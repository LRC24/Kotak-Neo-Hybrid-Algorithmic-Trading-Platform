import logging
from ..logging import api_logger

# Known Kotak Neo API Error Codes and messages
ERROR_MAPPINGS = {
    '100008': "Static IP is not whitelisted for trading. Please log in to the Kotak Neo developer portal and add your outbound IP address to your application settings.",
    '10506': "Invalid TOTP code. Please double-check your authenticator app and try again.",
    '10507': "Invalid UCC or credentials. Please check your UCC/Mobile settings in .env.",
    '5203': "No Data Found / Empty Response.",
}

def parse_api_error(response) -> str:
    """
    Parses Kotak API response structures to extract clear, human-readable error descriptions.
    """
    if response is None:
        return "API returned empty (None) response."
        
    if isinstance(response, str):
        return response
        
    if isinstance(response, dict):
        # Check for 'error' list
        err_list = response.get('error') or response.get('Error')
        if err_list:
            if isinstance(err_list, list) and len(err_list) > 0:
                first_err = err_list[0]
                code = str(first_err.get('code', ''))
                msg = first_err.get('message', 'Unknown Error')
                return ERROR_MAPPINGS.get(code, f"Error {code}: {msg}")
            return str(err_list)
            
        # Check for 'errMsg' / 'emsg' in dict
        err_msg = response.get('errMsg') or response.get('emsg') or response.get('desc')
        st_code = str(response.get('stCode', ''))
        
        if err_msg:
            # Match specific whitelisting errors
            if 'unauthorized' in str(err_msg).lower() or st_code == '100008':
                return ERROR_MAPPINGS['100008']
            if 'data not found' in str(err_msg).lower() or st_code == '5203':
                return ERROR_MAPPINGS['5203']
                
            return ERROR_MAPPINGS.get(st_code, f"API Error (stCode: {st_code}): {err_msg}")
            
        # Check for general 'status' or 'stat'
        if 'stat' in response and response['stat'].lower() != 'ok':
            return response.get('stat', 'Error')
            
    return "Unknown API communication error."
