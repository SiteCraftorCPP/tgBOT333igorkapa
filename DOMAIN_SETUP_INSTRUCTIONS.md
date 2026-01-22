# 🌐 Настройка домена enguerrados.com

Полная инструкция по настройке домена для коротких ссылок оплаты.

---

## 1️⃣ Настройка DNS (где купил домен)

Зайди в панель управления доменом (Namecheap/Cloudflare/etc) и добавь эти **A-записи**:

```
Тип: A
Имя: @
Значение: IP_ТВОЕГО_VPS
TTL: 3600

Тип: A
Имя: pay
Значение: IP_ТВОЕГО_VPS
TTL: 3600

Тип: A  
Имя: www
Значение: IP_ТВОЕГО_VPS
TTL: 3600
```

**Подожди 5-30 минут** пока DNS обновится.

Проверить можно командой:
```bash
ping pay.enguerrados.com
```

---

## 2️⃣ Установка Nginx (на VPS)

```bash
# Подключись к VPS
ssh root@твой_ip

# Установи Nginx
sudo apt update
sudo apt install nginx -y

# Запусти Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## 3️⃣ Настройка Nginx для редиректов

Создай конфиг для домена:

```bash
sudo nano /etc/nginx/sites-available/enguerrados
```

Вставь это:

```nginx
# Redirect сервер для коротких ссылок
server {
    listen 80;
    server_name pay.enguerrados.com;

    # Логи
    access_log /var/log/nginx/enguerrados-redirect-access.log;
    error_log /var/log/nginx/enguerrados-redirect-error.log;

    # Проксируем на redirect_server.py (порт 8001)
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Webhook сервер
server {
    listen 80;
    server_name enguerrados.com www.enguerrados.com;

    # Логи
    access_log /var/log/nginx/enguerrados-webhook-access.log;
    error_log /var/log/nginx/enguerrados-webhook-error.log;

    # Проксируем на webhook_server.py (порт 5000)
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Сохрани (**Ctrl+O**, **Enter**, **Ctrl+X**)

Активируй конфиг:

```bash
sudo ln -s /etc/nginx/sites-available/enguerrados /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 4️⃣ Установка SSL (Let's Encrypt)

```bash
# Установи certbot
sudo apt install certbot python3-certbot-nginx -y

# Получи SSL сертификаты
sudo certbot --nginx -d enguerrados.com -d www.enguerrados.com -d pay.enguerrados.com

# Следуй инструкциям:
# - Введи email
# - Согласись с условиями (Y)
# - Выбери "2" (редирект на HTTPS)
```

Сертификат обновляется **автоматически** каждые 90 дней.

---

## 5️⃣ Обновление конфига бота

Обнови `.env` на VPS:

```bash
cd ~/tgBOT333igorkapa
nano .env
```

Измени:

```env
WEBHOOK_URL=https://enguerrados.com/webhook
```

**Важно:** замени `http://IP:5000` на `https://enguerrados.com`

---

## 6️⃣ Обновление short_link_generator.py

Обнови домен в файле:

```bash
nano short_link_generator.py
```

Строка 10:
```python
DOMAIN = "https://pay.enguerrados.com"  # ← было http://...
```

---

## 7️⃣ Установка redirect сервера

```bash
cd ~/tgBOT333igorkapa

# Подтяни изменения
git pull

# Запусти deploy скрипт
bash deploy_redirect_server.sh
```

---

## 8️⃣ Перезапуск всех сервисов

```bash
sudo systemctl restart enguerrados-bot
sudo systemctl restart enguerrados-webhook
sudo systemctl restart enguerrados-redirect
sudo systemctl restart enguerrados-auto-check
```

---

## 9️⃣ Проверка

```bash
# Проверь что всё работает
sudo systemctl status enguerrados-redirect

# Тест короткой ссылки (замени на реальный код)
curl -I https://pay.enguerrados.com/test123
# Должен вернуть 404 (нормально, ссылки ещё нет)

# Проверь логи
sudo journalctl -u enguerrados-redirect -f
```

---

## 🎯 Результат

**Было:**
```
https://checkout.stripe.com/c/pay/cs_live_a14IoKBn2UJaZKRotbDldAR0cebtDh5joxj5Y27TFra3CzPOrzDju88pCZ#fidnandhYHdWcXxpYCc%2FJ2FgY2RwaXEnKSdkdWxOYHwnPyd1blppbHNgWjA0VlxQTjxEVGZvaE1PTTF8T2cyaWNIVGMxbHxJVH08QFdUU2FPZk12fVZ1c3JyQHA2b2ZoPHNia0FENkpHVX00VXZtZjNiZ0o8XGM9Z2BjaHVxdUZffUJhNTVjNjRBcV99bCcpJ2N3amhWYHdzYHcnP3F3cGApJ2dkZm5id2pwa2FGamlqdyc%2FJyZjY2NjY2MnKSdpZHxqcHFRfHVgJz8ndmxrYmlgWmxxYGgnKSdga2RnaWBVaWRmYG1qaWFgd3YnP3F3cGB4JSUl
```

**Стало:**
```
https://pay.enguerrados.com/1m-a7xK9mPq
https://pay.enguerrados.com/6m-bN4tRw2s
https://pay.enguerrados.com/12m-cY8vXm5p
```

✅ **Короткие, красивые, брендированные!**

---

## 🔧 Troubleshooting

### DNS не резолвится
```bash
# Проверь DNS
nslookup pay.enguerrados.com
dig pay.enguerrados.com
```

### Nginx ошибки
```bash
# Проверь конфиг
sudo nginx -t

# Логи
sudo tail -f /var/log/nginx/error.log
```

### Redirect сервер не работает
```bash
# Логи
sudo journalctl -u enguerrados-redirect -f

# Перезапуск
sudo systemctl restart enguerrados-redirect
```

---

**Готово!** Теперь ссылки выглядят профессионально 🔥
