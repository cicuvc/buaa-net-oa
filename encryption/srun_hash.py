"""SRUN MD5 wrapper"""

import hmac
import hashlib

def get_md5(password,token):
    """Calculate HMAC MD5"""
    return hmac.new(token.encode(), password.encode(), hashlib.md5).hexdigest()

if __name__ == '__main__':
    TEST_PWD="15879684798qq"
    TEST_TOKEN="711ab370231392679fe06523b119a8fe096f5ed9bd206b4de8d7b5b994bbc3e5"
    print(get_md5(TEST_PWD,TEST_TOKEN))

def get_sha1(value):
    """Calculate SHA1"""
    return hashlib.sha1(value.encode()).hexdigest()

if __name__ == '__main__':
    print(get_sha1("123456"))
