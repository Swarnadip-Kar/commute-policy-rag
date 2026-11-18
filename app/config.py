import os
from pathlib import Path
JWT_SECRET = os.getenv('JWT_SECRET', 'dev-secret-change-me')
JWT_ALGO = 'HS256'
DATA_DIR = Path(os.getenv('DATA_DIR', './data'))
EMBED_BACKEND = os.getenv('EMBED_BACKEND', 'minilm') # 'hash' in tests
RETRIEVAL_MODE = os.getenv('RETRIEVAL_MODE', 'vector') # 'hybrid' in Step 13
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.groq.com/openai/v1')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
LLM_TIMEOUT_S = float(os.getenv('LLM_TIMEOUT_S', '2.0'))
USE_FAKE_LLM = os.getenv('USE_FAKE_LLM', '0') == '1'
TOP_K = 3 # chunks retrieved
MAX_CITED = 3 # chunks cited (case-study limit)
MAX_LLM_CALLS = 2 # case-study limit
RETRY_ONLY_IF_UNDER_S = 1.0
RETRIEVAL_TIMEOUT_S = 1.0