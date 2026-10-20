# Masha Imports: Hub update (keeps your database, photos and hotels)

This package has EVERY code file and NO data (no db.sqlite3, media/ or .env).

Install with Terminal (merges folders; Finder "Replace" would delete files):

    cd ~/Desktop
    cp MASHA/db.sqlite3 db.backup.sqlite3
    ditto ~/Downloads/masha-complete-code-v2/MASHA ~/Desktop/MASHA
    cd ~/Desktop/MASHA
    python3 manage.py migrate
    python3 manage.py runserver

Do NOT run makemigrations; the migration files are included.

Then open http://127.0.0.1:8000/hub/ and sign in with your admin (staff) account.
Go to Settings → "Chat & WhatsApp" to add your WhatsApp number.

To give a team member access: Hub → Customers → open them → "Edit account"
→ tick "Staff status" (they can then use the hub).
