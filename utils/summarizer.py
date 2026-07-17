import aiosqlite
from config import DB_PATH
from utils.logger import logger
from utils.llm import generate_response
from database import get_setting

async def maybe_summarize_thread(thread_id: str, threshold: int = 30):
    """
    Kalau jumlah pesan di thread > threshold:
    1. Ambil semua pesan yang belum ter-summarize (id > covers_up_to terakhir)
    2. Kirim ke LLM (model default) minta ringkasan singkat
    3. Simpan/update thread_summaries
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Cek Covers up to
            covers_up_to = 0
            existing_summary = ""
            async with db.execute('SELECT summary, covers_up_to FROM thread_summaries WHERE thread_id = ?', (thread_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    existing_summary = row["summary"]
                    covers_up_to = row["covers_up_to"]
                    
            # Ambil pesan setelah covers_up_to
            async with db.execute('''
                SELECT id, role, content FROM conversations 
                WHERE thread_id = ? AND id > ? AND role IN ('user', 'assistant')
                ORDER BY id ASC
            ''', (thread_id, covers_up_to)) as cursor:
                rows = await cursor.fetchall()
                
            if len(rows) <= threshold:
                return # Belum mencapai threshold
                
            logger.info(f"Summarizing thread {thread_id} with {len(rows)} new messages...")
            
            new_last_id = rows[-1]["id"]
            
            # Build text to summarize
            conversation_text = ""
            for r in rows:
                conversation_text += f"{r['role'].upper()}: {r['content']}\n\n"
                
            prompt = "Ringkas percakapan berikut secara singkat namun informatif. "
            if existing_summary:
                prompt += f"Ini adalah ringkasan sebelumnya:\n{existing_summary}\n\nPerbarui ringkasan ini dengan menambahkan informasi dari percakapan terbaru berikut:\n"
            else:
                prompt += "Berikut adalah percakapannya:\n"
                
            messages = [{"role": "user", "content": prompt + conversation_text}]
            
            model_alias = await get_setting('default_model') or "gemini"
            
            new_summary = await generate_response(model_alias, messages, system_prompt="Anda adalah sistem peringkas konteks. Berikan ringkasan yang objektif, jelas, singkat, dan mencakup semua poin penting yang telah didiskusikan.")
            
            # Simpan ke DB
            await db.execute('''
                INSERT INTO thread_summaries (thread_id, summary, covers_up_to, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(thread_id) DO UPDATE SET summary=excluded.summary, covers_up_to=excluded.covers_up_to, updated_at=datetime('now')
            ''', (thread_id, new_summary, new_last_id))
            
            await db.commit()
            
    except Exception as e:
        logger.error(f"Error summarizing thread {thread_id}: {e}")
