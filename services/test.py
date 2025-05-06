import tiktoken
from dotenv import load_dotenv

load_dotenv()

enc = tiktoken.get_encoding("cl100k_base")
print(enc.encode("hello world"))
print(enc.decode([15496, 995]))
print(enc.decode([15496, 995, 100257]))
