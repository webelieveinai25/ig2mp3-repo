# Guida GitHub Actions - Build Automatico Windows EXE

## 🚀 Setup Iniziale

### 1. Crea il Repository GitHub
1. Vai su [GitHub.com](https://github.com) e accedi
2. Clicca "New repository" (pulsante verde)
3. Nome: `ig2mp3-repo` (o quello che preferisci)
4. Seleziona "Public" (gratuito)
5. **NON** selezionare "Add a README file" (lo abbiamo già)
6. Clicca "Create repository"

### 2. Carica i File
```bash
# Nel terminale, dalla cartella ig2mp3-repo
git init
git add .
git commit -m "Initial commit: Instagram to MP3 converter"
git branch -M main
git remote add origin https://github.com/TUOUSERNAME/ig2mp3-repo.git
git push -u origin main
```

**Sostituisci `TUOUSERNAME` con il tuo username GitHub!**

## 🔄 Build Automatico

### Metodo 1: Push Automatico
Ogni volta che fai push sul branch `main`, il build parte automaticamente.

### Metodo 2: Manuale
1. Vai su GitHub → tuo repository
2. Clicca tab "Actions"
3. Clicca "Build Windows EXE" (a sinistra)
4. Clicca "Run workflow" (pulsante blu)
5. Clicca "Run workflow" (conferma)

## 📦 Download del Risultato

1. Vai su tab "Actions"
2. Clicca sull'ultimo workflow completato (✓ verde)
3. Scorri in basso fino a "Artifacts"
4. Clicca su `ConvertiIG2MP3_windows` per scaricare
5. Estrai il file ZIP

## 📁 Contenuto del Pacchetto

Il file ZIP contiene:
- `ConvertiIG2MP3.exe` - Il programma principale
- `ffmpeg.exe` - Convertitore audio (incluso)
- `README.txt` - Istruzioni rapide
- `links.txt` - File di esempio per i link

## 🎯 Distribuzione

1. Invia il file ZIP ai collaboratori
2. Istruzioni per loro:
   - Estrai tutto in una cartella
   - Doppio-click su `ConvertiIG2MP3.exe`
   - Incolla i link Instagram
   - I MP3 saranno in `output_mp3/`

## 🔧 Troubleshooting

### Build Fallisce
- Controlla i log in Actions → workflow → "build" step
- Verifica che tutti i file siano presenti
- Controlla che il workflow YAML sia corretto

### EXE Non Funziona
- Assicurati che `ffmpeg.exe` sia nella stessa cartella
- Prova a eseguire da riga di comando per vedere errori
- Controlla che Windows Defender non blocchi l'exe

### Aggiornamenti
Per aggiornare il programma:
1. Modifica `converti_instagram_mp3.py`
2. Commit e push su GitHub
3. Il build automatico creerà la nuova versione

## 💡 Suggerimenti

- **Versioning**: Aggiungi tag per le versioni importanti
- **Releases**: Crea GitHub Releases per distribuzione facile
- **Backup**: Mantieni sempre una copia locale del codice
- **Testing**: Testa sempre l'exe prima di distribuirlo

## 🔗 Link Utili

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [PyInstaller Documentation](https://pyinstaller.org/)
- [yt-dlp Repository](https://github.com/yt-dlp/yt-dlp)
