import sys
import traceback

files_to_check = [
    'commands.bate_ponto',
    'commands.membros',
    'commands.verificacao',
    'utils',
    'database',
    'config'
]

for f in files_to_check:
    try:
        __import__(f)
        print(f"OK: {f}")
    except Exception as e:
        print(f"ERROR in {f}: {e}")
        traceback.print_exc()
