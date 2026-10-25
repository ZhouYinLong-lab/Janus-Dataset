"""Small OpenAI-compatible HTTP adapter. No SDK, automatic retries or redirects."""
import json
import urllib.error
import urllib.parse
import urllib.request


class RequestFailure(Exception):
    def __init__(self,kind,http_status=None,ambiguous=False):
        super().__init__(kind)
        self.kind,self.http_status,self.ambiguous=kind,http_status,ambiguous


def check_config(config):
    expected={'base_url','model','api_key_env','timeout_seconds','max_output_tokens',
              'output_token_parameter','response_format','max_requests','max_reserved_tokens'}
    if set(config)!=expected:raise ValueError('Config has missing/unknown keys; secrets belong only in environment')
    url=urllib.parse.urlsplit(config['base_url'])
    local=url.hostname in {'localhost','127.0.0.1','::1'}
    if (url.scheme!='https' and not (url.scheme=='http' and local)) or not url.hostname:
        raise ValueError('HTTPS required, except explicit localhost integration tests')
    if url.username or url.password or url.query or url.fragment:
        raise ValueError('base_url must not contain credentials, query or fragment')
    if not isinstance(config['model'],str) or not config['model'].strip() or 'REPLACE_' in config['model']:
        raise ValueError('Set an actual provider model ID')
    if not isinstance(config['api_key_env'],str) or not config['api_key_env'].isidentifier():
        raise ValueError('api_key_env must be an environment variable name')
    for name in ['timeout_seconds','max_output_tokens','max_requests','max_reserved_tokens']:
        if type(config[name]) is not int or config[name]<1:raise ValueError(name+' must be a positive integer')
    if config['output_token_parameter'] not in {'max_tokens','max_completion_tokens'}:
        raise ValueError('Unsupported output token parameter')
    if config['response_format'] not in {'json_object','none'}:raise ValueError('Unsupported response_format')


def make_request(job,prompt,config):
    # No local filesystem paths, labels or old audit answers are sent to a provider.
    evidence={k:job[k] for k in ['paper_id','doi','title','scope_hypothesis','primary_units',
                                'context_units','context_omitted_units','primary_chunk_index','paper_primary_chunks']}
    payload={'model':config['model'],'messages':[{'role':'system','content':prompt},
             {'role':'user','content':json.dumps(evidence,ensure_ascii=False)}],
             'stream':False,config['output_token_parameter']:config['max_output_tokens']}
    if config['response_format']=='json_object':payload['response_format']={'type':'json_object'}
    return payload


def reserve_tokens(request,config):
    # Conservative operational estimate, NOT an exact provider tokenizer/billing cap.
    return sum(len(m['content'].encode('utf-8')) for m in request['messages'])+2048+config['max_output_tokens']


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise RequestFailure('redirect_blocked',code,ambiguous=True)


class HTTPClient:
    def __init__(self,config,key):
        self.config,self.key=config,key
        self.opener=urllib.request.build_opener(NoRedirect())

    def complete(self,payload):
        req=urllib.request.Request(self.config['base_url'].rstrip('/')+'/chat/completions',
            data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},method='POST')
        try:
            with self.opener.open(req,timeout=self.config['timeout_seconds']) as response:
                raw=response.read(16_000_001)
                if len(raw)>16_000_000:raise RequestFailure('response_too_large',ambiguous=True)
        except urllib.error.HTTPError as exc:
            # Do not log error bodies or request objects: providers can echo credentials.
            raise RequestFailure('http_error',exc.code,ambiguous=False) from None
        except (urllib.error.URLError,TimeoutError,ConnectionError,OSError):
            raise RequestFailure('network_outcome_unknown',ambiguous=True) from None
        try:
            return json.loads(raw.decode('utf-8'))
        except (ValueError,UnicodeError):
            raise RequestFailure('non_json_http_response',ambiguous=True) from None


def parse_completion(envelope):
    if not isinstance(envelope,dict):raise ValueError('API envelope must be an object')
    choices=envelope.get('choices')
    if not isinstance(choices,list) or len(choices)!=1:raise ValueError('Expected one API choice')
    choice=choices[0]
    if choice.get('finish_reason')!='stop':raise ValueError('Response did not finish normally; never treat as empty extraction')
    content=choice.get('message',{}).get('content')
    if not isinstance(content,str):raise ValueError('Expected textual JSON content')
    def unique_pairs(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(content,object_pairs_hook=unique_pairs)
