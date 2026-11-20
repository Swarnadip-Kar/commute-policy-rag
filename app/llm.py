import json
import re

import httpx


class LLMError(Exception):
    '''The LLM call failed: network, timeout, quota or a malformed response.'''


class OpenAICompatLLM:
    '''Works with Groq, Gemini's OpenAI-compatible endpoint, or a local server.'''

    def __init__(self, base_url, api_key, model, timeout_s):
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def complete(self, system, user):
        body = {'model': self.model, 'temperature': 0, 'max_tokens': 300,
                'response_format': {'type': 'json_object'},   # remove if your provider rejects it
                'messages': [{'role': 'system', 'content': system},
                             {'role': 'user', 'content': user}]}
        try:
            r = httpx.post(self.url, json=body, timeout=self.timeout_s,
                           headers={'Authorization': f'Bearer {self.api_key}'})
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
            raise LLMError(str(e)) from e


CHUNK = re.compile(r'<CHUNK id="([^"]+)">(.*?)</CHUNK>', re.S)


def _default_handler(system, user):
    '''Fake behaviour: answer with the first chunk it is shown.'''
    m = CHUNK.search(user)
    if not m:
        return json.dumps({'covered': False, 'answer': '', 'cited_ids': [], 'evidence': ''})
    cid, text = m.group(1), m.group(2).strip()
    return json.dumps({'covered': True, 'answer': text[:300],
                       'cited_ids': [cid], 'evidence': text[:80]})


class FakeLLM:
    '''For tests. handler(system, user) returns a string, or an Exception to be raised.'''

    def __init__(self, handler=None):
        self.handler = handler or _default_handler
        self.calls = 0

    def complete(self, system, user):
        self.calls += 1
        out = self.handler(system, user)
        if isinstance(out, Exception):
            raise out
        return out