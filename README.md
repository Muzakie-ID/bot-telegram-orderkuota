# Telegram PPOB Bot (Python & Docker)

Bot Telegram sederhana untuk melakukan transaksi PPOB (Pulsa, Kuota, Token PLN) menggunakan API H2H OkeConnect. Dibangun dengan Python (Flask) dan berjalan di atas Docker.

## Fitur
- 🔎 **Cek Harga & Kategori:** Mencari produk berdasarkan kategori atau kata kunci.
- 🚀 **Order Cepat:** Mendukung multi-nomor tujuan (disimpan di config).
- 💰 **Cek Saldo:** Real-time check saldo OkeConnect.
- 📖 **Pagination:** Tampilan daftar harga yang rapi dengan navigasi halaman.
- 🐳 **Dockerized:** Mudah dijalankan di mana saja.

## Cara Instalasi

### 1. Clone Repository
```bash
git clone https://github.com/Muzakie-ID/bot-telegram-orderkuota
cd ppob-bot

```

### 2. Konfigurasi

Copy file contoh environment:

```bash
cp .env.example .env

```

Lalu edit file `.env` dan isi dengan **Token Bot Telegram** dan **Akun OkeConnect** Anda.

### 3. Jalankan dengan Docker

```bash
docker compose up -d --build

```

## Teknologi

* Python 3.9
* Flask
* Docker & Docker Compose
