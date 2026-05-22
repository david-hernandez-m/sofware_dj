# MiniDJ Controller Lab

MiniDJ Controller Lab es un software DJ/VJ experimental desarrollado en Python. Está pensado como una base educativa para reproducir audio/video, probar una interfaz tipo DJ y mapear controladores MIDI USB.

> Proyecto independiente. No está afiliado ni respaldado por marcas comerciales de software DJ ni fabricantes de controladores.

## Funciones principales

- Interfaz oscura estilo DJ/VJ.
- Dos decks de reproducción.
- Soporte para audio y video.
- Carga de MP4, MOV, MKV, AVI, WEBM, MP3, WAV, OGG, FLAC, M4A y AAC.
- Biblioteca multimedia con búsqueda.
- Crossfader de audio.
- Salida principal de video.
- Vista previa por deck.
- Hot cues 1 al 4 por deck.
- BPM manual.
- Sampler interno.
- Soporte MIDI usando `pygame.midi`.
- Modo aprender para mapear botones, faders y perillas de controladores MIDI USB.

## Requisitos

- Windows 10/11.
- Python 3.11 o 3.12 recomendado.
- VS Code recomendado.
- Controlador MIDI USB compatible, opcional.

## Instalación rápida en Windows

Desde PowerShell, dentro de la carpeta del proyecto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python main.py
```

También puedes ejecutar:

```powershell
.\install_windows.ps1
```

## Dependencias

```txt
PySide6>=6.7
pygame-ce>=2.5.7
```

## Archivos generados automáticamente

La aplicación puede crear estos archivos al ejecutarse:

- `library.json`: biblioteca local de medios.
- `hotcues.json`: hot cues guardados.
- `mapping.json`: asignaciones MIDI.
- `samples/`: samples WAV internos generados por la app.

Estos archivos están excluidos del repositorio mediante `.gitignore` porque dependen del uso local de cada usuario.

## Formatos recomendados

Para video, se recomienda usar MP4 con video H.264 y audio AAC para mayor compatibilidad.

## Estado del proyecto

Versión inicial lista para GitHub. El proyecto es funcional como prototipo, pero todavía puede mejorar en áreas como análisis real de waveform, detección automática de BPM, loops, efectos DSP y mezcla visual avanzada.

## Licencia

Distribuido bajo licencia MIT. Consulta el archivo `LICENSE`.
