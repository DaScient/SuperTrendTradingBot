import json
from copy import copy

__all__ = ['MessageData', 'SELL_MSG', 'BUY_MSG', 'ORDER_MSG']

class MessageData(object):

    def __init__(self, template, name='MessageData'):
        self._template = template
        self._name = name
        for k, v in self._template.items():
            if isinstance(v, dict):
                v = MessageData(v, name='.'.join([self._name, k]))
            self.__dict__[k] = v
    
    def __repr__(self):
        return f'{self._name}'
        
    def to_json(self):
        keys = [k for k in self.__dict__.keys() if not k.startswith('_')]
        data = {k: self.__dict__.get(k) for k in keys}
        nested = {k: v for k, v in data.items() if not isinstance(v, str)}
        if nested:
            body = nested.get('body', '')
            if body:
                keys = [k for k in body.__dict__.keys() if not k.startswith('_')]
                contents = {k: body.__dict__.get(k) for k in keys}
            else:
                contents = copy(body)
            data['body'] = contents
        return json.dumps(data)

ORDER_MSG = {'name': '',
             'type': 'ORDER',
             'body': {'action': '',
                      'symbol': '',
                      'amount': None,
                      'indicator': ''}
             }
        
SELL_MSG = {'name': '',
            'type': 'ORDER',
            'body': {'action': 'SELL',
                     'symbol': '',
                     'amount': None,
                     'indicator': ''}
            }
BUY_MSG = {'name': '',
           'type': 'ORDER',
           'body': {'action': 'BUY',
                    'symbol': '',
                    'amount': None,
                    'indicator': ''}
           }

if __name__ == '__main__':
    template = {'name': '', 'type': '', 'body': {'action': '', 'symbol': '', 'amount': None}}
    message = MessageData(template)
    message.name = 'master'
    message.type = 'order'
    message.body.action = 'BUY'
    message.body.symbol = 'GOOG'
    message.body.amount = 100
    print(message.to_json())