import re

# Lee el archivo
with open('utils/stream_reader.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remover emojis de las líneas de logger
emoji_map = {
    '🎯': '[OK]',
    '📻': '[RADIO]',
    '📡': '[SIGNAL]',
    '🎵': '[MUSIC]',
    '🎤': '[AUDIO]',
    '❌': '[ERROR]',
    '✅': '[SUCCESS]',
    '🔍': '[CHECK]',
    '🔎': '[CHECK]',
    '🎸': '[GENRE]',
    '⏭️': '[SKIP]',
    '💾': '[SAVE]',
    '⚠️': '[WARN]',
    '═': '=',
    '─': '-'
}

for emoji, text in emoji_map.items():
    content = content.replace(emoji, text)

# Escribe
with open('utils/stream_reader.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('[OK] Emojis removidos de stream_reader.py')
