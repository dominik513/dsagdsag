import random
import string

def generate_lobby() -> tuple[str, str, str]:
    match_id = ''.join(random.choices(string.digits, k=10))
    lobby_name = f"DT{random.randint(1000, 9999)}"
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return match_id, lobby_name, password
