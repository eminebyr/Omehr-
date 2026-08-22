# tests/ — başlangıç test iskeleti

Bu paketin önceki bir sürümünde "58/58 test geçti" iddiası vardı, ama bu
zip'te hiçbir test dosyası, `TESTLERI_CALISTIR.bat`, `YESIL_PAKET_TESTI.bat`
veya `tests/` klasörü bulunmuyordu — o iddia bu paket için doğrulanamıyordu.
Bu klasör, **sıfırdan, küçük bir başlangıç** olarak eklendi.

## Kapsam (bugün gerçekten test edilen)

- `services/settings.py` — merkezi input dosya adı ayarı
- `services/runtime_paths.py` — izole çalışma zamanı kökü, tenant kodu
- `services/exceptions.py` — özel hata sınıfı hiyerarşisi
- `services/safe_exec.py` — "sessiz hata" loglama katmanı (log_swallowed/swallow)
- `services/schema_validation.py` — fail-fast şema sözleşmesi
- `src/state_engine.state()` + `src/kpi_engine.kpis()` — norm motorunun
  temel aritmetiği, el ile hesaplanmış küçük bir örnekle doğrulandı
- Gerçek bir `.xlsx` dosyası üretip okuyan mini uçtan-uca test
  (`test_sample_workbook.py`)

Tümü **izole** çalışır: `conftest.py`'deki `isolated_root` fixture'ı
`OMEHR_RUNTIME_ROOT` ortam değişkenini her testte geçici bir klasöre
yönlendirir — testler gerçek `input/`, `output/`, `data/`, `logs/`
klasörlerinize KESİNLİKLE dokunmaz.

## Kapsam DIŞI (bu turda yapılmadı, gerçek ortam gerektiriyor)

- Web paneli (Streamlit çalışma zamanı bu sandbox'ta yok)
- PDF üretimi (reportlab bu sandbox'ta yok)
- Outlook/SMTP gönderimi (gerçek posta sunucusu/Outlook profili gerekir)
- LibreOffice formül yeniden hesaplama
- `main.py`'nin tam uçtan uca çalıştırılması (yukarıdakilerin hepsine bağımlı)
- Orijinal "58 test" ile bire bir eşleşme — o testlerin içeriği elimizde
  değildi, burada YENİDEN yazılmadı

## Çalıştırma

```bash
pip install -r requirements.txt   # pytest zaten requirements.txt'te var
pytest
```

veya kısayol:

```bash
./TESTLERI_CALISTIR.sh        # Linux/Mac
TESTLERI_CALISTIR.bat         # Windows
```

## Sırada ne var

Bu iskelet üstüne eklenebilecek en değerli sıradaki testler:
1. Transfer onay akışının durum makinesi (`services/transfer_lifecycle.py`)
   — bekliyor → bölge onayı → İK onayı → tamamlandı geçişleri
2. `services/security.py` — parola kuralları, kilitleme, PBKDF2 doğrulaması
3. AI norm üst sınırı (`src/ai_norm.py`) — önerinin normun 1,20 katını
   aşmadığının doğrulanması
4. Gerçek `main.py` çalıştırması — yalnız CI'da (LibreOffice + reportlab
   kurulu bir ortamda) mümkün, bu sandbox'ta değil
