import sqlite3
import os

db_path = "faccao.db"

def migrate():
    if not os.path.exists(db_path):
        print("Banco de dados não encontrado.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Tenta adicionar a coluna tipo_menu
        cursor.execute("ALTER TABLE ticket_paineis ADD COLUMN tipo_menu TEXT DEFAULT 'select'")
        print("Coluna tipo_menu adicionada com sucesso.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Coluna tipo_menu já existe.")
        else:
            print(f"Erro ao adicionar coluna: {e}")
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
