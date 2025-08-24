# Instagram to MP3 Converter

Convertitore di video Instagram in MP3 con interfaccia grafica e riga di comando, basato su yt-dlp.

## 🚀 Caratteristiche

- **Interfaccia grafica** semplice e intuitiva
- **Riga di comando** per automazione
- **Download batch** da file di testo
- **Qualità configurabile** (128-320 kbps)
- **Gestione errori** con log dettagliati
- **Supporto metadati** e thumbnail
- **Rate limiting** per evitare blocchi
- **Retry automatico** con backoff esponenziale

## 📦 Download

### Windows (Raccomandato)
1. Vai su [Actions](https://github.com/tuousername/ig2mp3-repo/actions)
2. Clicca su "Build Windows EXE" → "Run workflow"
3. Scarica l'artifact `ConvertiIG2MP3_windows.zip`
4. Estrai e doppio-click su `ConvertiIG2MP3.exe`

### Manuale
```bash
git clone https://github.com/tuousername/ig2mp3-repo.git
cd ig2mp3-repo
pip install -r requirements.txt
python converti_instagram_mp3.py
```

## 🎯 Uso Rapido

### GUI (Doppio-click)
1. Doppio-click su `ConvertiIG2MP3.exe`
2. Incolla i link Instagram o carica `links.txt`
3. I file MP3 saranno salvati in `output_mp3/`

### CLI
```bash
# Singolo link
python converti_instagram_mp3.py --url "https://www.instagram.com/reel/XXXX/"

# Batch da file
python converti_instagram_mp3.py --links links.txt --out cartella_output

# Qualità personalizzata
python converti_instagram_mp3.py --url "https://..." --quality 256
```

## 📝 Formato links.txt

```
https://www.instagram.com/reel/XXXX/
https://www.instagram.com/p/YYYY/
# Commenti iniziano con #
https://www.instagram.com/stories/username/ZZZZ/
```

## ⚙️ Opzioni Avanzate

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `--quality` | Qualità MP3 (128/192/256/320) | 320 |
| `--sleep` | Secondi tra download | 1.0 |
| `--retries` | Tentativi per URL | 3 |
| `--rate-limit` | Limite velocità (es. "1M") | Nessuno |
| `--thumbnail` | Includi thumbnail | No |
| `--archive` | File per saltare già scaricati | downloaded.txt |

## 🔧 Requisiti

- **Windows**: Nessuno (tutto incluso nell'exe)
- **Altri OS**: Python 3.8+, ffmpeg, yt-dlp

## 📊 Output

- **File MP3**: Nome formato `uploader-title-id.mp3`
- **errors.log**: Errori dettagliati per debug
- **report.csv**: Report CSV con status download
- **downloaded.txt**: Archivio URL già processati

## 🛠️ Build Locale

```bash
# Installa dipendenze
pip install yt-dlp pyinstaller

# Build exe
pyinstaller --onefile --noconsole --name ConvertiIG2MP3 converti_instagram_mp3.py

# Aggiungi ffmpeg.exe nella stessa cartella
```

## 🧪 Test

```bash
python converti_instagram_mp3.py --run-tests
```

## 📄 Licenza

MIT License - vedi [LICENSE](LICENSE)

## 🤝 Contributi

1. Fork il repository
2. Crea un branch per la feature
3. Commit le modifiche
4. Push al branch
5. Apri una Pull Request

## ⚠️ Disclaimer

Questo tool è per uso personale. Rispetta i termini di servizio di Instagram e i diritti d'autore.

## 🔗 Link Utili

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Engine di download
- [FFmpeg](https://ffmpeg.org/) - Conversione audio
- [Instagram](https://instagram.com) - Piattaforma sorgente
