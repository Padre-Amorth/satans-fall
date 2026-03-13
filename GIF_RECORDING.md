# GIF Recording Feature

## Utilizzo

**Avvia registrazione**: Premi **F11**
- Console stampa: `[GIF] Registrazione avviata — premi F11 per fermare`
- Tutti i frame vengono catturati automaticamente

**Ferma registrazione e salva**: Premi **F11** di nuovo
- Console stampa: `[GIF] Salvato: recordings/clip_YYYYMMDD_HHMMSS.gif (N frame, S.Ts, M.M MB)`
- La GIF è pronta in `recordings/`

**Auto-stop**: Se la registrazione supera 60 secondi, si ferma automaticamente e salva.

## Configurazione

Le impostazioni si trovano in `src/game_constants.py`:

```python
GIF_RECORDING_FPS = 15          # FPS della GIF (1 frame ogni 4 @ 60fps)
GIF_MAX_DURATION_SECONDS = 60   # Durata massima in secondi
GIF_SCALE_FACTOR = 0.5          # Scala (0.5 = 640x360, riduce file size)
```

### Adattare i parametri

- **FPS della GIF**: 15 è buono per clip standard. Aumentare a 20-24 per maggiore fluidità (file più grandi).
- **Durata massima**: 60 secondi è standard. Aumentare se vuoi clip più lunghe.
- **Scala**: 0.5 produce GIF da ~640x360. Usare 0.75 per 960x540 (file più grandi) o 0.33 per 420x240 (molto piccoli).

## File modificati

1. **src/game_constants.py**: Aggiunto costanti GIF
2. **src/game/core.py**: Aggiunto hook di acquisizione frame nel game loop
3. **src/systems/input_handler.py**:
   - Aggiunto state per GIF (`__init__`)
   - Aggiunto binding F11 (`handle_keydown`)
   - Aggiunto `_toggle_gif_recording()` - avvia/ferma
   - Aggiunto `_capture_gif_frame()` - cattura frame
   - Aggiunto `_save_gif()` - salva GIF

## Dipendenze

- **Pillow** (PIL) - utilizzato per creare GIF. Già installato nel progetto.

## Caratteristiche

✓ Toggle on/off con F11
✓ Campionamento frame intelligente (1 ogni 4 @ 60fps = 15fps output)
✓ Scaling automatico per ridurre file size (0.5x = 640x360)
✓ Auto-stop dopo 60 secondi (safety)
✓ Timestamp nei nomi file
✓ Feedback in console
✓ Funziona in qualsiasi schermata di gioco

## Esempi

```
Premi F11 → [GIF] Registrazione avviata — premi F11 per fermare
(gioca 10 secondi)
Premi F11 → [GIF] Salvato: recordings/clip_20260312_143025.gif (150 frame, 10.0s, 2.3 MB)
```

La GIF è pronta per condividere!
