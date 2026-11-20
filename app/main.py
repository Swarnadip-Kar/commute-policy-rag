import logging
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import config, embeddings
from .answer import answer_question
from .auth import require_admin, require_company
from .chunking import PolicyFormatError
from .ingest import IngestError, ingest_policy
from .llm import FakeLLM, OpenAICompatLLM
from .store import PolicyStore

log = logging.getLogger('api')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')


@asynccontextmanager
async def lifespan(app):
    if config.JWT_SECRET == 'dev-secret-change-me':
        log.warning('JWT_SECRET is the development default; set a real secret outside demos')
    embeddings.embed(['warm up'])      # load the model now, not on the first user's request
    yield


app = FastAPI(title='Commute Policy Assistant', lifespan=lifespan)


@lru_cache
def get_store():
    return PolicyStore(config.DATA_DIR)


@lru_cache
def get_llm():
    if config.USE_FAKE_LLM:
        return FakeLLM()
    return OpenAICompatLLM(config.LLM_BASE_URL, config.LLM_API_KEY,
                           config.LLM_MODEL, config.LLM_TIMEOUT_S)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')          # no company field, no surprises
    question: str = Field(min_length=1, max_length=500)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    company: str
    text: str = Field(min_length=1, max_length=200_000)


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/ask')
def ask(req: AskRequest, company: str = Depends(require_company),
        store=Depends(get_store), llm=Depends(get_llm)):
    if not req.question.strip():
        raise HTTPException(status_code=422, detail='question is empty')
    result = answer_question(store, llm, company, req.question)
    return JSONResponse(status_code=503 if result.status == 'error' else 200,
                        content=result.to_dict())


@app.post('/admin/policies')
def admin_ingest(req: IngestRequest, _claims: dict = Depends(require_admin),
                 store=Depends(get_store)):
    try:
        return ingest_policy(store, req.company, req.text)
    except (PolicyFormatError, IngestError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        log.exception('ingestion failed')
        raise HTTPException(status_code=500, detail='ingestion failed; the active policy is unchanged')