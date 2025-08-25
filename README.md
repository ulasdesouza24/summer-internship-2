## Akıllı Proje Dokümantasyonu Asistanı (Neo4j + Gemini + MCP-benzeri Köprü)

Bu proje; kod tabanınızı, bağımlılıkları ve geliştirici bilgilerini Neo4j'e bir bilgi grafiği olarak yükler; Gemini (Google Generative AI) ile bu grafı sorgulayıp tarayıcıdan cevap almanızı sağlar.

### Stack
- **Veritabanı**: Neo4j (Desktop veya AuraDB)
- **LLM**: Gemini 1.5 Pro (function calling)
- **Köprü Sunucu**: FastAPI (`/execute_cypher_query`, `/ask`, `/ui`, `/diag/gemini`)
- **Dil**: Python 3.10+

### Kurulum
1) Python 3.10+ kurulu olsun.
2) Neo4j Desktop/AuraDB veritabanı oluşturun.
3) Ortam değişkenleri:
   - `env.example` → `.env` kopyalayın ve doldurun.
   - Gerekli anahtarlar: `NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE, GEMINI_API_KEY, MCP_READ_ONLY`
4) Bağımlılıklar:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Ontoloji (Şema)
- **Düğümler**
  - `Gelistirici(isim,email,team)`
  - `Modul(dosya_yolu,dil)`
  - `Fonksiyon(id,isim,parametreler,geri_donus_tipi,satir,dosya_yolu)`
  - `Kutuphane(isim,versiyon)`
- **İlişkiler**
  - `YAZDI(Gelistirici->Modul)`
  - `ICERIR(Modul->Fonksiyon)`
  - `CAGIRIR(Fonksiyon->Fonksiyon)`
  - `KULLANIR(Modul->Kutuphane)`
Not: Alan adı `dosya_yolu`dur. `dosya_adi` yoktur.

Not: Etiket ve ilişki adları ASCII kullanır (Türkçe diakritik yok) ve Cypher ile uyumludur.

### Veri Yükleme (Ingestion)
```bash
python -m src.ingest.ingest --root C:\path\to\your\python-project --include-dev true
```
- Python dosyalarındaki modüller, fonksiyonlar, importlar çıkarılır.
- Repo ise `git blame` ile geliştirici bilgileri eklenir.

### Köprü Sunucuyu Çalıştırma (MCP benzeri)
```bash
uvicorn src.server.main:app --host 0.0.0.0 --port 8000
```
- Swagger: `http://localhost:8000/docs`
- Basit UI: `http://localhost:8000/ui`
- Sağlık: `GET /health`, Tanı: `GET /diag/gemini`
- Varsayılan: yalnızca READ-ONLY (`MCP_READ_ONLY=true`).

### Gemini İstemcisi (Tool Use)
Örnek bir soru sorup Gemini'nin aracı çağırmasını sağlamak için:
```bash
python -m src.gemini.client --question "auth.py modülünü hangi geliştiriciler yazdı?" --server http://localhost:8000
```

### Adım 4 Akış Örneği (Gemini ile)
1. **Kullanıcı sorar**: "auth.py modülünü hangi geliştiriciler yazdı?"
2. **LLM analiz eder** ve aşağı gibi Cypher üretir:
   ```
   MATCH (g:Gelistirici)-[:YAZDI]->(m:Modul {dosya_yolu: "auth.py"})
   RETURN g.isim AS isim, g.email AS email
   ```
3. **LLM, tool use ile** `execute_cypher_query` fonksiyonunu çağırır.
4. **Köprü Sunucu**, Neo4j üzerinde sorguyu çalıştırır ve sonucu JSON döner.
5. **LLM**, sonucu doğal dil cevaba dönüştürür: "auth.py üzerinde Ayşe Yılmaz (ayse@...) ve Ali Kaya (ali@...) çalışmış."

### Tarayıcıdan Sorma
- `http://localhost:8000/ui` → sorunuzu yazın → Sor
- Örnek: `main.py dosyasını kim yazdı?` veya tam yol ile sorun.

### Yazma İşlemleri (Opsiyonel)
1) `.env` → `MCP_READ_ONLY=false`, sunucuyu yeniden başlatın
2) Örnek ilişki ekleme:
```json
{ "query": "MERGE (g:Gelistirici {email:'dev@example.com'}) SET g.isim='Örnek Geliştirici' WITH g MATCH (m:Modul) WHERE m.dosya_yolu ENDS WITH 'src\\\\server\\\\main.py' MERGE (g)-[:YAZDI]->(m)" }
```
3) Doğrulama:
```json
{ "query": "MATCH (m:Modul) WHERE m.dosya_yolu ENDS WITH 'src\\\\server\\\\main.py' MATCH (g:Gelistirici)-[:YAZDI]->(m) RETURN g.isim, g.email" }
```
4) Güvenlik: tekrar `MCP_READ_ONLY=true` yapın.

### Sorun Giderme
- `GET /diag/gemini` → `ok:true` olmalı (API anahtarı)
- `/ask` hata verirse `detail` alanına bakın.
- Sonuç çıkmıyorsa dosya yolunu `ENDS WITH` ile test edin:
```json
{ "query": "MATCH (m:Modul) WHERE m.dosya_yolu ENDS WITH 'main.py' MATCH (g:Gelistirici)-[:YAZDI]->(m) RETURN g.isim, g.email" }
```
- Repo değilse `git blame` geliştirici çıkaramaz; ilişkiyi elle ekleyin.


