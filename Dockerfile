# Gunakan Python versi ringan
FROM python:3.9-slim

# Set zona waktu ke WIB (Jakarta)
ENV TZ=Asia/Jakarta
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Buat folder kerja
WORKDIR /app

# Copy requirements dan install library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh source code
COPY . .

# Expose port Flask
EXPOSE 5000

# Jalankan aplikasi
CMD ["python", "main.py"]
