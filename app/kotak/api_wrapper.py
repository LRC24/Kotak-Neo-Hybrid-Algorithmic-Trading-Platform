import logging
from typing import Optional, Dict, Any
from neo_api_client import NeoAPI
from ..logging import api_logger
from .error_handler import parse_api_error

class KotakAPIWrapper:
    # Wraps the official Kotak Neo API SDK client to add clean logging, automatic parameter formatting, and unified exception handling.
    
    def __init__(self, client: NeoAPI):
        self.client = client
        self.max_retries = 3
        self.retry_delay = 2

    def _check_response(self, response: Any, operation: str) -> dict:
        # Helper to inspect API responses and raise custom errors on failure states
        if response is None:
            raise ValueError(f"{operation} returned empty (None) response.")
            
        # Parse error state if applicable
        if isinstance(response, str) or (isinstance(response, dict) and ('error' in response or 'Error' in response or ('stat' in response and response['stat'].lower() != 'ok'))):
            err_msg = parse_api_error(response)
            # Treat "No Data" as empty success instead of hard failure
            if "No Data" in err_msg or "5203" in err_msg:
                api_logger.debug(f"{operation} returned empty result: {err_msg}")
                return {}
            api_logger.error(f"{operation} failed: {err_msg}")
            raise ValueError(err_msg)
            
        return response if isinstance(response, dict) else {}

    def login_with_totp(self, mobile_number: str, ucc: str, totp: str) -> dict:
        # Step 1 of the login flow: Submits mobile number, UCC client code, and manual TOTP code
        try:
            api_logger.info("Executing Kotak TOTP authentication step 1...")
            response = self.client.totp_login(
                mobile_number=mobile_number,
                ucc=ucc,
                totp=totp
            )
            return self._check_response(response, "TOTP Login Step 1")
        except Exception as e:
            api_logger.error(f"TOTP Login Step 1 exception: {e}", exc_info=True)
            raise

    def validate_totp(self, mpin: str) -> dict:
        # Step 2 of the login flow: Submits MPIN to complete session token generation.
        try:
            api_logger.info("Executing Kotak MPIN validation step 2...")
            response = self.client.totp_validate(mpin=mpin)
            parsed_res = self._check_response(response, "MPIN Validation Step 2")
            
            data = parsed_res.get("data", {})
            sid = data.get("sid")
            token = data.get("token")
            server_id = data.get("hsServerId") or sid # Fallback to sid if missing
            
            if not sid or not token:
                raise ValueError("MPIN validation succeeded but response is missing token credentials (sid/token).")
                
            # Bind session tokens back into SDK configuration
            self.client.configuration.edit_sid = sid
            self.client.configuration.edit_token = token
            self.client.configuration.serverId = server_id
            
            api_logger.info(f"Session authenticated successfully. Session ID: {sid} | Server ID: {server_id}")
            return parsed_res
            
        except Exception as e:
            api_logger.error(f"MPIN Validation Step 2 exception: {e}", exc_info=True)
            raise

    def place_order(self, **order_params) -> dict:
        # Places order with auto-casting of numeric fields (price, quantity) to strings to prevent SDK parameter validation crashes.
        try:
            api_logger.info(f"Placing order for symbol: {order_params.get('trading_symbol')}")
            
            # Cast numeric parameters to string
            for field in ('price', 'trigger_price', 'quantity', 'disclosed_quantity', 'market_protection'):
                if field in order_params and order_params[field] is not None:
                    order_params[field] = str(order_params[field])
                    
            response = self.client.place_order(**order_params)
            return self._check_response(response, "Place Order")
            
        except Exception as e:
            api_logger.error(f"API place_order exception: {e}", exc_info=True)
            raise

    def modify_order(self, order_id: str, **modify_params) -> dict:
        # Modifies order parameters, performing string casting on modified inputs
        try:
            api_logger.info(f"Modifying order ID: {order_id}")
            
            for field in ('price', 'trigger_price', 'quantity'):
                if field in modify_params and modify_params[field] is not None:
                    modify_params[field] = str(modify_params[field])
                    
            response = self.client.modify_order(order_id=order_id, **modify_params)
            return self._check_response(response, "Modify Order")
            
        except Exception as e:
            api_logger.error(f"API modify_order exception: {e}", exc_info=True)
            raise

    def cancel_order(self, order_id: str, amo: str = 'NO', isVerify: bool = False) -> dict:
        # Cancels order by ID
        try:
            api_logger.info(f"Cancelling order ID: {order_id}")
            response = self.client.cancel_order(order_id=order_id, amo=amo, isVerify=isVerify)
            return self._check_response(response, "Cancel Order")
        except Exception as e:
            api_logger.error(f"API cancel_order exception: {e}", exc_info=True)
            raise

    def get_positions(self) -> list:
        # Retrieves open position book list
        try:
            response = self.client.positions()
            res_dict = self._check_response(response, "Get Positions")
            return res_dict.get("data", []) if isinstance(res_dict, dict) else []
        except Exception as e:
            api_logger.error(f"API get_positions exception: {e}", exc_info=True)
            return []

    def get_orders(self) -> list:
        # Retrieves active day order book log list
        try:
            response = self.client.order_report()
            res_dict = self._check_response(response, "Get Order Report")
            return res_dict.get("data", []) if isinstance(res_dict, dict) else []
        except Exception as e:
            api_logger.error(f"API get_orders exception: {e}", exc_info=True)
            return []

    def get_limits(self) -> dict:
        # Retrieves fund balances and trading margins metadata
        try:
            response = self.client.limits()
            return self._check_response(response, "Get Limits")
        except Exception as e:
            api_logger.error(f"API get_limits exception: {e}", exc_info=True)
            raise

    def get_scrip_master(self, exchange_segment: str = 'nse_fo') -> dict:
        # Downloads dynamic file containing scrip master mapping from Kotak servers
        try:
            api_logger.info(f"Downloading Scrip Master CSV for segment: {exchange_segment}...")
            response = self.client.scrip_master(exchange_segment=exchange_segment)
            if response is None:
                raise ValueError("Scrip Master download returned None.")
            return response
        except Exception as e:
            api_logger.error(f"API get_scrip_master exception: {e}", exc_info=True)
            raise

    def logout(self):
        # Logs out session cleanly
        try:
            self.client.logout()
        except Exception as e:
            api_logger.warning(f"Error logging out Kotak API wrapper: {e}")
