import os
from cloudflare import Cloudflare

def update_local_ip(api_email: str, api_token: str, api_key: str, new_ip: str) -> bool:
    try:
        client = Cloudflare(
            # This is the default and can be omitted
            api_email=api_email,
            # This is the default and can be omitted
            api_token = api_token,
            api_key=api_key
        )

        acc_id = client.accounts.list().result[0]['id']

        namespaces = client.kv.namespaces.list(account_id=acc_id).result
        ns_id = [i.id for i in namespaces if i.title == 'xn-ip'][0]
        
        client.kv.namespaces.values.update('ip', account_id=acc_id, namespace_id=ns_id, metadata='{}', value=new_ip)

        return True
    except Exception as e:
        return False
