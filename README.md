# Rose Valley - Zabravih 🗑️

Динамична система за следене на количеството боклук, прогнозира кога те ще се напълнят и създава ефикасни динамични маршрути за боклукчийските камиони.

## За проекта

Проектът включва:
- Django backend, хостван на Debian 13 с Gunicorn, Nginx и Cloudflare Tunnel
- Raspberry Pi с трениран pattern recognition, камера и NFC четец, с цел мерене на боклука в кофите
- Визуализация на кофите с топлинни карти динамични маршрути в реално време
- Feedback loop алгоритъм за планиране на събиране
- RESTful API за връзка между Raspberry-то и backend-a


### Как работи

1. **AI Измерване**: Raspberry Pi с камера разпознава нивото на запълване чрез TensorFlow Lite модел
2. **NFC Идентификация**: Екипът за събиране сканира NFC таг на кошчето за записване на събирането
3. **Обработка на данни**: Django обработва подадената информация и изчислява процент на запълване
4. **Визуализация**: Real-time топлинни карти показват статуса на кошчетата в града
5. **Оптимизация на маршрути**: Системата генерира оптимизирани маршрути чрез OpenRouteService



## Технологии

<p align="left">
  <a href="https://www.djangoproject.com/" target="_blank"><img src="https://img.shields.io/badge/Django-092E20?style=for-the-badge&logo=django&logoColor=white" /></a>
  <a href="https://www.postgresql.org/" target="_blank"><img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white" /></a>
  <a href="https://www.tensorflow.org/" target="_blank"><img src="https://img.shields.io/badge/TensorFlow_Lite-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white" /></a>
  <a href="https://teachablemachine.withgoogle.com/" target="_blank"><img src="https://img.shields.io/badge/Teachable_Machine-4285F4?style=for-the-badge&logo=google&logoColor=white" /></a>
  <a href="https://opencv.org/" target="_blank"><img src="https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" /></a>
  <a href="https://www.raspberrypi.org/" target="_blank"><img src="https://img.shields.io/badge/Raspberry_Pi-A22846?style=for-the-badge&logo=raspberry-pi&logoColor=white" /></a>
  <a href="https://flask.palletsprojects.com/" target="_blank"><img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" /></a>
  <a href="https://python-visualization.github.io/folium/" target="_blank"><img src="https://img.shields.io/badge/Folium-77B829?style=for-the-badge&logo=leaflet&logoColor=white" /></a>
  <a href="https://openrouteservice.org/" target="_blank"><img src="https://img.shields.io/badge/OpenRouteService-2D7A9B?style=for-the-badge&logo=openstreetmap&logoColor=white" /></a>
  <a href="https://getbootstrap.com/" target="_blank"><img src="https://img.shields.io/badge/Bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white" /></a>
  <a href="https://cloudflare.com/" target="_blank"><img src="https://img.shields.io/badge/Cloudflare_Tunnel-F38020?style=for-the-badge&logo=cloudflare&logoColor=white" /></a>
  <a href="https://www.debian.org/" target="_blank"><img src="https://img.shields.io/badge/Debian-A81D33?style=for-the-badge&logo=debian&logoColor=white" /></a>
  <a href="https://gunicorn.org/" target="_blank"><img src="https://img.shields.io/badge/Gunicorn-499848?style=for-the-badge&logo=gunicorn&logoColor=white" /></a>
  <a href="https://nginx.org/" target="_blank"><img src="https://img.shields.io/badge/Nginx-009639?style=for-the-badge&logo=nginx&logoColor=white" /></a>
  <a href="https://pandas.pydata.org/" target="_blank"><img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white" /></a>
  <a href="https://numpy.org/" target="_blank"><img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white" /></a>
</p>

## Функционалности/Компоненти

### AI Разпознаване
- **Computer vision**: TensorFlow Lite модел класифицира нивото на запълване на кофите
- **Праг на доверие**: Само високодоверителни предикции се изпращат към сървъра

### Локализация на NFC
- **RFID**: MFRC522 NFC четец с цел идентификация на кошчета
- **Логване на събиране**: Автоматично записване при изпразване

### Алгоритъм за пълнене
- **Изчисляване на процент запълване**: Пресмятане на дневния коефициент на запълване за всяко кошче
- **Прогноза за напълване**: Предвижда кога кошчетата ще достигнат почти пълен капацитет
- **Историческо осредняване**: Използва 30-дневен прозорец, с цел намиране на абнормални стойности на пълнене

### Динамична маршрутизация
- **Разделяне на няколко маршрута**: Създаване на няколко маршрута според капацитета на камионите
- **Nearest-Neighbor алгоритъм**: Маршрутизиращ алгоритъм за fuel efficeincy на камиона
- **OpenRouteService x Folium**: Достоверни маршрути с визуализация в реално време

### Информационно табло
- **Топлинна карта**: Визуално представяне на нивата на кофите в града, в реално време
- **Статистики и нива на критичност**: Полезна информация предсавена на лесно място





## 🌍 **Live Demo**: [https://zabravih.org](https://zabravih.org)


## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                  Raspberry Pi (Edge Device)                     │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│   │    Камера    │  │   NFC Четец  │  │   TensorFlow Lite  │    │
│   │    (RTSP)    │  │   (MFRC522)  │  │  (Teachable Model) │    │
│   └──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘    │
│          │                 │                    │               │
│          └─────────────────┴────────────────────┘               │
│                            │                                    │
│                     ┌──────▼───────┐                            │
│                     │ Flask Server │                            │
│                     │ (Port 5000)  │                            │
│                     └──────┬───────┘                            │
└────────────────────────────┼────────────────────────────────────┘
                             │ HTTPS (SSL)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Django Server (Selfhosted on R630)           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   Nginx Reverse Proxy                    │   │
│  │              (SSL/TLS via Cloudflare Tunnel)             │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │                  Gunicorn WSGI Server                    │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │                Django Application                        │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │   │
│  │  │   Models    │  │    Views     │  │   REST API     │   │   │
│  │  │ (TrashCan,  │  │ (Maps, Route │  │ (/api/update/) │   │   │
│  │  │ FillRecord) │  │ Optimization)│  │                │   │   │
│  │  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘   │   │
│  └─────────┼────────────────┼──────────────────┼────────────┘   │
│            │                │                  │                │
│  ┌─────────▼────────────────▼──────────────────▼────────────┐   │
│  │                  PostgreSQL Database                     │   │
│  │  • Локации и метаданни на кошчета                        │   │
│  │  • История на нива на запълване (time-series)            │   │
│  │  • Изчислени проценти и предикции                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```
