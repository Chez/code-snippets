# Copyright 2015 Google Cloud Platform Book ISBN - 978-1-4842-1005-5_Krishnan_Ch01_The Basics of Cloud Computing
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import md5
import sys
import time
import json

from OpenSSL.crypto import load_pkcs12, load_privatekey, FILETYPE_PEM, sign
import requests

GCS_API_ENDPOINT = 'https://storage.googleapis.com'

#### Do not expose the following information -JSON_KEY_PATH, SERVICE_ACCOUNT_EMAIL, PRIVATE_KEY_PATH- in production environments. 
#### You can this in a configuration file.

# Use this variable when using a JSON key file downloaded from Google Developer Console
JSON_KEY_PATH = '<path-to-your-json-key-file.json>' 

# Use these variables when downloading the P12 key file directly from Google Developer Console
SERVICE_ACCOUNT_EMAIL = '<service-account-email>' # *@developer.gserviceaccount.com'
PRIVATE_KEY_PATH = '<path-to-your-pkcs-key.p12>' 

class GCSUrlSigner(object):

    def __init__(self, key, client_id_email, expiration=None):
        """
        Keyword arguments:
            key: The private key - OpenSSL::PKey - used to sign the content.
            client_id_email: Email form of the client ID for GCS.
            expiration: An instance of datetime.datetime with the time when the signed URL should expire.
        """
        self.private_key = key.get_privatekey()
        self.client_id_email = client_id_email

        self.expiration = expiration or (datetime.datetime.now() + datetime.timedelta(days=1))
        self.expiration = int(time.mktime(self.expiration.timetuple()))


    def _construct_signature_string(self, verb, path, content_type, content_md5):
        """ Create the signature string for signing according to the documentation.

        Keyword arguments:
            verb: HTTP verb to use in the request.
            path: The path to the object inside of its bucket: '/bucket/object'.
            content_md5: Requests with body shall specify the md5 of the its content.
            content_type: Requests with body can specify the content type.

        Return the signature string itself.
        """
        signature_string_skeleton = ('{verb}\n'
                                     '{content_md5}\n'
                                     '{content_type}\n'
                                     '{expiration}\n'
                                     '{resource}')

        return signature_string_skeleton.format(verb=verb,
                                                content_md5=content_md5,
                                                content_type=content_type,
                                                expiration=self.expiration,
                                                resource=path)


    def sign(self, verb, path, content_type='', content_md5=''):
        """ Compose a signed URL to access GCS.

        Return:
            base_url: The absolute url to access the resource.
            query_parameters: The associated params as specified by the signed urls protocol.
        """
        base_url = '%s%s' % (GCS_API_ENDPOINT, path)

        signature_string = self._construct_signature_string(verb, path, content_type, content_md5)
        signed_signature = sign(self.private_key, signature_string, 'sha256')
        encoded_signature = base64.b64encode(signed_signature)

        query_parameters = {'GoogleAccessId': self.client_id_email,
                            'Expires': str(self.expiration),
                            'Signature': encoded_signature}

        return base_url, query_parameters


'''  
This sample code composes a signer object used to construct signed urls according to the specified params.
In this the following test case, a new object is created and uploaded to Datastore to be further read, both through signed urls.
Thus, note that no authorization mechanisms are needed once the signed url is generated.
'''

def mockSignedPut(signer):

    resource = '/lunchmates_document_dropbox/hello_world.txt' #/<bucket_name>/<object_name>
    content_type = 'text/plain'
    content = 'Hello World!'
    md5_digest = base64.b64encode(md5.new(content).digest())

    signed_url, query_parameters = signer.sign('PUT', resource, content_type, md5_digest)
  
    headers = {}
    headers['Content-Type'] = content_type
    headers['Content-Length'] = str(len(content))
    headers['Content-MD5'] = md5_digest

    response = requests.put(signed_url, params=query_parameters, headers=headers, data=content)
    if response.status_code == 200:
        print 'Put file successfully.'
    else:
        print 'Error ' + response.status_code


def mockSignedGet(signer):
    resource = '/lunchmates_document_dropbox/hello_world.txt' #/<bucket_name>/<object_name>
    signed_url, query_parameters = signer.sign('GET', resource)
  
    response = requests.get(signed_url, params=query_parameters)
    if response.status_code == 200:
        print 'Read contents of file:\n' + response.text
    else:
        print 'Error ' + response.status_code


def main():

    use_json_key = JSON_KEY_PATH is not None and JSON_KEY_PATH != '<path-to-your-json-key-file.json>'

    try:
        key_text = open(JSON_KEY_PATH if use_json_key else PRIVATE_KEY_PATH, 'rb').read()
    except IOError as e:
        sys.exit('Error while reading private key: %s' % e)

    if use_json_key:
        json_key = json.loads(key_text)
        private_key = load_privatekey(FILETYPE_PEM, json_key['private_key'])
        client_email = json_key['client_email']
    else:
        private_key = load_pkcs12(key_text, 'notasecret').get_privatekey() # 'notasecret' is the default password for Google-generated PKCS keys.
        client_email = SERVICE_ACCOUNT_EMAIL


    expiration = datetime.datetime.now() + datetime.timedelta(hours = 12)
    url_signer = GCSUrlSigner(private_key, SERVICE_ACCOUNT_EMAIL, expiration)

    mockSignedPut(url_signer)
    mockSignedGet(url_signer)
  

if __name__ == '__main__':
    main()