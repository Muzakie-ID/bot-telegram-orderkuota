import os
from flask import Flask, request
import requests, time, json, math

app = Flask(__name__)

# ================= KONFIGURASI =================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Config OkeConnect
OKE_MEMBER_ID = os.getenv('OKE_MEMBER_ID')
OKE_PIN = os.getenv('OKE_PIN')
OKE_PASSWORD = os.getenv('OKE_PASSWORD')
OKE_BASE_URL = 'https://h2h.okeconnect.com/trx'
PRICELIST_URL = os.getenv('PRICELIST_URL')

# Parsing Daftar Nomor
raw_nomor = os.getenv('NOMOR_TUJUAN', '')
LIST_NOMOR = [num.strip() for num in raw_nomor.split(',') if num.strip()]

# Memory & Database
last_trx = {"refid": None, "dest": None, "product": None}
PRODUK_DB = {} 
KATEGORI_LIST = [] 
USER_STATES = {} 

# Limit Item Per Halaman
ITEMS_PER_PAGE = 20

# ================= FUNGSI BANTUAN =================
def send_telegram(text, keyboard=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    if keyboard: payload['reply_markup'] = json.dumps(keyboard)
    try: 
        resp = requests.post(url, json=payload, timeout=5)
        return resp.json()
    except Exception as e:
        print(f"❌ Gagal kirim pesan: {e}")
        return None

def delete_telegram_message(message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {'chat_id': CHAT_ID, 'message_id': message_id}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def answer_callback(callback_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    try: requests.post(url, json={'callback_query_id': callback_id}, timeout=5)
    except: pass

def format_rupiah(angka):
    try:
        return f"Rp {int(float(angka)):,}".replace(",", ".")
    except:
        return str(angka)

def get_back_menu_button():
    return [{"text": "🔙 Kembali ke Menu", "callback_data": "btn_back_menu"}]

def get_back_kategori_button():
    return [{"text": "🔙 Kembali ke Kategori", "callback_data": "btn_cek_harga"}]

# ================= SYNC & KATEGORI LOGIC =================
def sync_produk():
    global PRODUK_DB, KATEGORI_LIST
    print("⏳ Sync Produk dimulai...")
    try:
        resp = requests.get(PRICELIST_URL, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            TEMP_DB = {} 
            temp_kategori = set() 
            
            for item in data:
                kode = item.get('kode')
                nama = item.get('keterangan') or item.get('produk') or kode
                kategori = item.get('kategori') or "LAIN-LAIN"
                kategori = kategori.upper()

                try: harga = float(item.get('harga', 0))
                except: harga = 0
                
                status_raw = str(item.get('status', '0'))
                status = 1 if status_raw == '1' else 0

                if kode:
                    TEMP_DB[kode] = {
                        "nama": nama, 
                        "harga": harga, 
                        "status": status,
                        "kategori": kategori
                    }
                    temp_kategori.add(kategori)
            
            PRODUK_DB = TEMP_DB 
            KATEGORI_LIST = sorted(list(temp_kategori))
            
            print(f"✅ Sync Selesai! {len(PRODUK_DB)} produk, {len(KATEGORI_LIST)} kategori.")
            return True
        else:
            print("❌ Gagal download JSON.")
            return False
    except Exception as e:
        print(f"❌ Error Sync: {e}")
        return False

def cari_produk(keyword):
    if len(keyword) < 3: return "⚠️ Kata kunci minimal 3 huruf."
    keyword = keyword.lower()
    
    hasil = []
    count = 0
    
    for kode, info in PRODUK_DB.items():
        if (keyword in kode.lower() or 
            keyword in info['nama'].lower() or 
            keyword in info['kategori'].lower()):
            
            status_icon = "✅" if info['status'] == 1 else "❌"
            hrg = format_rupiah(info['harga'])
            hasil.append(f"{status_icon} `{kode}` : {hrg}\n{info['nama']}")
            count += 1
            if count >= 15: break 
    
    if hasil:
        return f"🔎 **HASIL PENCARIAN '{keyword}'**:\n\n" + "\n\n".join(hasil)
    else:
        return f"❌ Produk '{keyword}' tidak ditemukan."

# ================= API OKECONNECT =================
def api_cek_saldo():
    try:
        url = f"{OKE_BASE_URL}/balance"
        params = {'memberID': OKE_MEMBER_ID, 'pin': OKE_PIN, 'password': OKE_PASSWORD}
        resp = requests.get(url, params=params, timeout=10)
        return resp.text
    except Exception as e: return f"Error: {e}"

def api_order(kode_produk, nomor_tujuan):
    try:
        if not kode_produk: return "❌ Kode produk kosong."
        kode_produk = kode_produk.upper()
        
        detail = PRODUK_DB.get(kode_produk)
        nama_display = detail['nama'] if detail else kode_produk
        ref_id = f"AUTO{int(time.time())}"
        
        params = {
            'memberID': OKE_MEMBER_ID, 'pin': OKE_PIN, 'password': OKE_PASSWORD,
            'product': kode_produk, 'dest': nomor_tujuan, 'refID': ref_id
        }
        resp = requests.get(OKE_BASE_URL, params=params, timeout=10)
        global last_trx
        last_trx.update({"refid": ref_id, "dest": nomor_tujuan, "product": kode_produk})
        
        if "akan diproses" in resp.text or "SUKSES" in resp.text:
            return f"🚀 **ORDER DIKIRIM**\n📦 {nama_display}\n📱 `{nomor_tujuan}`\n🆔 `{ref_id}`\n\nRespon: {resp.text}"
        return f"⚠️ **GAGAL/PENDING**\n{resp.text}"
    except Exception as e: return f"Error: {e}"

def api_status():
    try:
        if last_trx['refid'] is None: return "⚠️ Belum ada transaksi."
        detail = PRODUK_DB.get(last_trx['product'])
        nama_display = detail['nama'] if detail else last_trx['product']
        params = {
            'memberID': OKE_MEMBER_ID, 'pin': OKE_PIN, 'password': OKE_PASSWORD,
            'product': last_trx['product'], 'dest': last_trx['dest'],
            'refID': last_trx['refid'], 'check': '1'
        }
        resp = requests.get(OKE_BASE_URL, params=params, timeout=10)
        return f"📊 **STATUS TRANSAKSI**\n📦 {nama_display}\n🆔 `{last_trx['refid']}`\n\nRespon:\n{resp.text}"
    except Exception as e: return f"Error: {e}"

# ================= LOGIKA WEBHOOK =================
@app.route('/telegram_webhook', methods=['POST'])
def telegram_webhook():
    data = request.json
    
    # --- 1. HANDLE PESAN TEKS ---
    if 'message' in data:
        msg = data['message']
        chat_id = str(msg.get('chat', {}).get('id'))
        if chat_id != str(CHAT_ID): return "Unauthorized", 403
        
        text = msg.get('text', '').strip()
        msg_id = msg.get('message_id')
        time.sleep(0.5) 
        delete_telegram_message(msg_id) 

        if text.lower() in ['/start', '/menu']:
            if chat_id in USER_STATES: del USER_STATES[chat_id]
            keyboard = {
                "inline_keyboard": [
                    [{"text": "💰 Cek Saldo", "callback_data": "btn_saldo"}],
                    [{"text": "🚀 Order Kuota", "callback_data": "btn_pilih_nomor"}],
                    [{"text": "🔎 Cek Harga", "callback_data": "btn_cek_harga"}], 
                    [{"text": "📊 Cek Status Trx", "callback_data": "btn_status"}],
                    [{"text": "🔄 Sync Produk", "callback_data": "btn_sync"}]
                ]
            }
            send_telegram("🤖 **PANEL PPOB OTOMATIS**", keyboard)
            return "OK", 200

        user_state = USER_STATES.get(chat_id)
        if user_state:
            step = user_state.get('step')
            prompt_id = user_state.get('prompt_id')
            if prompt_id: delete_telegram_message(prompt_id)

            if step == 'WAIT_SEARCH':
                keyword = text.lower()
                hasil = cari_produk(keyword)
                send_telegram(hasil, {"inline_keyboard": [get_back_kategori_button()]})
                del USER_STATES[chat_id]

            elif step == 'WAIT_NUMBER':
                if text.isdigit() and len(text) > 9:
                    nomor_manual = text
                    sent = send_telegram(f"✅ Tujuan: `{nomor_manual}`\n\n📝 **Ketik KODE PRODUK-nya:**")
                    if sent:
                        USER_STATES[chat_id] = {'step': 'WAIT_PRODUCT', 'selected_number': nomor_manual, 'prompt_id': sent['result']['message_id']}
                else:
                    sent = send_telegram("❌ Nomor salah (Angka Only). Ulangi:")
                    if sent: USER_STATES[chat_id]['prompt_id'] = sent['result']['message_id']

            elif step == 'WAIT_PRODUCT': 
                nomor_tujuan = user_state.get('selected_number')
                kode_produk = text.upper()
                keyboard = {"inline_keyboard": [get_back_menu_button()]}
                send_telegram(f"⏳ Order **{kode_produk}** ke `{nomor_tujuan}`...", keyboard)
                hasil = api_order(kode_produk, nomor_tujuan)
                send_telegram(hasil, keyboard)
                del USER_STATES[chat_id] 

            return "OK", 200

    # --- 2. HANDLE TOMBOL (CALLBACK) ---
    elif 'callback_query' in data:
        cb = data['callback_query']
        chat_id = str(cb['message']['chat']['id'])
        msg_id_menu = cb['message']['message_id']
        
        if chat_id != str(CHAT_ID): return "Unauthorized", 403
        answer_callback(cb['id'])
        data_btn = cb['data']
        delete_telegram_message(msg_id_menu)

        keyboard_back = {"inline_keyboard": [get_back_menu_button()]}

        if data_btn == 'btn_saldo': 
            send_telegram(f"💰 **SALDO**\n{api_cek_saldo()}", keyboard_back)
        elif data_btn == 'btn_status': 
            send_telegram("⏳ Cek Status...", keyboard_back)
            send_telegram(api_status(), keyboard_back)
        elif data_btn == 'btn_sync':
            send_telegram("⏳ Sedang download data...", keyboard_back)
            if sync_produk(): send_telegram(f"✅ Update Sukses: {len(PRODUK_DB)} produk.", keyboard_back)
            else: send_telegram("❌ Gagal sync.", keyboard_back)

        # === FITUR PILIH KATEGORI ===
        elif data_btn == 'btn_cek_harga':
            keyboard_cat = []
            row = []
            for kat in KATEGORI_LIST:
                label = (kat[:18] + '..') if len(kat) > 18 else kat
                # Format Data: pg_NAMAKATEGORI_HALAMAN
                # Kita mulai dari halaman 0
                row.append({"text": label, "callback_data": f"pg_{kat}_0"})
                if len(row) == 2:
                    keyboard_cat.append(row)
                    row = []
            if row: keyboard_cat.append(row)
            
            keyboard_cat.append([{"text": "🔍 Cari Manual (Ketik)", "callback_data": "btn_search_manual"}])
            keyboard_cat.append(get_back_menu_button())
            
            send_telegram("📂 **PILIH KATEGORI PRODUK:**", {"inline_keyboard": keyboard_cat})

        elif data_btn == 'btn_search_manual':
            sent = send_telegram("🔎 **MODE PENCARIAN**\n\nKetik nama/kode produk (Contoh: `axis`, `5gb`):")
            if sent:
                USER_STATES[chat_id] = {'step': 'WAIT_SEARCH', 'prompt_id': sent['result']['message_id']}

        # === FITUR PAGINATION (HALAMAN) ===
        elif data_btn.startswith('pg_'):
            # Format: pg_NAMAKATEGORI_HALAMAN (Contoh: pg_KUOTA XL_0)
            # Kita perlu memisahkan string dengan hati-hati karena Kategori bisa mengandung spasi atau underscore
            parts = data_btn.split('_')
            page = int(parts[-1]) # Angka terakhir adalah halaman
            kategori_pilih = "_".join(parts[1:-1]) # Gabungkan sisanya sebagai nama kategori
            
            # 1. Filter Produk sesuai Kategori
            list_produk = []
            for kode, info in PRODUK_DB.items():
                if info['kategori'] == kategori_pilih:
                    list_produk.append(info)
                    # Simpan kode di dalam info biar mudah akses nanti
                    list_produk[-1]['kode_asli'] = kode

            # 2. Logika Slicing (Potong Data)
            total_items = len(list_produk)
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
            
            start_idx = page * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            
            current_page_items = list_produk[start_idx:end_idx]

            # 3. Buat Teks Pesan
            msg_text = f"📂 **{kategori_pilih}** (Hal {page+1}/{total_pages})\n\n"
            if not current_page_items:
                msg_text += "❌ Tidak ada produk."
            else:
                for p in current_page_items:
                    icon = "✅" if p['status'] == 1 else "❌"
                    hrg = format_rupiah(p['harga'])
                    msg_text += f"{icon} `{p['kode_asli']}` : {hrg}\n{p['nama']}\n\n"

            # 4. Buat Tombol Navigasi (Prev - Back - Next)
            nav_buttons = []
            
            # Tombol Prev (Jika bukan halaman pertama)
            if page > 0:
                nav_buttons.append({"text": "⬅️ Prev", "callback_data": f"pg_{kategori_pilih}_{page-1}"})
            
            # Tombol Next (Jika belum halaman terakhir)
            if end_idx < total_items:
                nav_buttons.append({"text": "Next ➡️", "callback_data": f"pg_{kategori_pilih}_{page+1}"})

            keyboard = {
                "inline_keyboard": [
                    nav_buttons, # Baris Navigasi
                    [{"text": "🔙 Kembali ke Kategori", "callback_data": "btn_cek_harga"}]
                ]
            }
            
            send_telegram(msg_text, keyboard)

        # === FITUR ORDER ===
        elif data_btn == 'btn_pilih_nomor':
            keyboard_nomor = []
            for num in LIST_NOMOR:
                keyboard_nomor.append([{"text": f"📱 {num}", "callback_data": f"set_num_{num}"}])
            keyboard_nomor.append([{"text": "✍️ Input Manual", "callback_data": "btn_manual_num"}])
            keyboard_nomor.append(get_back_menu_button())
            send_telegram("🔢 **PILIH NOMOR TUJUAN**", {"inline_keyboard": keyboard_nomor})

        elif data_btn.startswith('set_num_'):
            nomor = data_btn.split('_')[2]
            sent = send_telegram(f"✅ Tujuan: `{nomor}`\n\n📝 **Ketik KODE PRODUK-nya:**")
            if sent: USER_STATES[chat_id] = {'step': 'WAIT_PRODUCT', 'selected_number': nomor, 'prompt_id': sent['result']['message_id']}

        elif data_btn == 'btn_manual_num':
            sent = send_telegram("✍️ **INPUT NOMOR**\n\nSilakan ketik nomor tujuan:")
            if sent: USER_STATES[chat_id] = {'step': 'WAIT_NUMBER', 'prompt_id': sent['result']['message_id']}
                
        elif data_btn == 'btn_back_menu':
             keyboard = {
                "inline_keyboard": [
                    [{"text": "💰 Cek Saldo", "callback_data": "btn_saldo"}],
                    [{"text": "🚀 Order Kuota", "callback_data": "btn_pilih_nomor"}],
                    [{"text": "🔎 Cek Harga", "callback_data": "btn_cek_harga"}], 
                    [{"text": "📊 Cek Status Trx", "callback_data": "btn_status"}],
                    [{"text": "🔄 Sync Produk", "callback_data": "btn_sync"}]
                ]
            }
             send_telegram("🤖 **PANEL PPOB OTOMATIS**", keyboard)

    return "OK", 200

@app.route('/callback_ppob', methods=['GET'])
def callback_ppob():
    refid = request.args.get('refid', '-')
    msg = request.args.get('message', '-')
    send_telegram(f"🔔 **CALLBACK**\nRefID: `{refid}`\nPesan: {msg}", {"inline_keyboard": [get_back_menu_button()]})
    return "OK", 200

sync_produk()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
