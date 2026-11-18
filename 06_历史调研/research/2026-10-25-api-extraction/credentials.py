"""Load one explicitly named credential; never execute .env text or print values."""
import os
from pathlib import Path


def load_key(name,env_file=None):
    if not isinstance(name,str) or not name.isidentifier():
        raise ValueError('Invalid API key environment variable name')
    if env_file is None:
        value=os.environ.get(name)
        if not value:raise ValueError('API key environment variable is unset')
        return value
    path=Path(env_file)
    if path.stat().st_size>65536:raise ValueError('Credential file unexpectedly large')
    matches=[]
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:].lstrip()
        key,separator,value=line.partition('=')
        if not separator or key.strip()!=name:continue
        value=value.strip()
        if value.startswith(('"',"'")):
            if len(value)<2 or value[-1]!=value[0]:raise ValueError('Unmatched quotes in credential assignment')
            value=value[1:-1]
        if not value or any(c.isspace() for c in value):raise ValueError('Credential value is empty or contains whitespace')
        matches.append(value)
    if len(matches)!=1:raise ValueError('Credential file must contain exactly one assignment for '+name)
    return matches[0]
