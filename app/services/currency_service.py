import requests
from typing import Dict, Optional, Tuple
from app.config import settings
import json

class CurrencyService:
    """Service for currency detection and conversion"""
    
    def __init__(self):
        self.country_currency_map = {
            # Major countries and their currencies
            "india": "INR",
            "united states": "USD", 
            "usa": "USD",
            "united kingdom": "GBP",
            "uk": "GBP",
            "canada": "CAD",
            "australia": "AUD",
            "germany": "EUR",
            "france": "EUR",
            "italy": "EUR",
            "spain": "EUR",
            "netherlands": "EUR",
            "japan": "JPY",
            "china": "CNY",
            "south korea": "KRW",
            "singapore": "SGD",
            "thailand": "THB",
            "malaysia": "MYR",
            "indonesia": "IDR",
            "philippines": "PHP",
            "vietnam": "VND",
            "brazil": "BRL",
            "mexico": "MXN",
            "argentina": "ARS",
            "chile": "CLP",
            "south africa": "ZAR",
            "egypt": "EGP",
            "turkey": "TRY",
            "russia": "RUB",
            "switzerland": "CHF",
            "norway": "NOK",
            "sweden": "SEK",
            "denmark": "DKK",
            "new zealand": "NZD",
            "israel": "ILS",
            "uae": "AED",
            "saudi arabia": "SAR",
            "qatar": "QAR",
            "kuwait": "KWD",
            "bahrain": "BHD",
            "oman": "OMR",
            "bangladesh": "BDT",
            "pakistan": "PKR",
            "sri lanka": "LKR",
            "nepal": "NPR",
            "bhutan": "BTN",
            "myanmar": "MMK",
            "cambodia": "KHR",
            "laos": "LAK",
            "mongolia": "MNT",
            "taiwan": "TWD",
            "hong kong": "HKD",
            "macau": "MOP"
        }
        
        # Currency symbols and names
        self.currency_info = {
            "INR": {"symbol": "₹", "name": "Indian Rupee"},
            "USD": {"symbol": "$", "name": "US Dollar"},
            "EUR": {"symbol": "€", "name": "Euro"},
            "GBP": {"symbol": "£", "name": "British Pound"},
            "JPY": {"symbol": "¥", "name": "Japanese Yen"},
            "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
            "AUD": {"symbol": "A$", "name": "Australian Dollar"},
            "SGD": {"symbol": "S$", "name": "Singapore Dollar"},
            "THB": {"symbol": "฿", "name": "Thai Baht"},
            "MYR": {"symbol": "RM", "name": "Malaysian Ringgit"},
            "IDR": {"symbol": "Rp", "name": "Indonesian Rupiah"},
            "PHP": {"symbol": "₱", "name": "Philippine Peso"},
            "VND": {"symbol": "₫", "name": "Vietnamese Dong"},
            "KRW": {"symbol": "₩", "name": "South Korean Won"},
            "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
            "HKD": {"symbol": "HK$", "name": "Hong Kong Dollar"},
            "TWD": {"symbol": "NT$", "name": "Taiwan Dollar"},
            "BRL": {"symbol": "R$", "name": "Brazilian Real"},
            "MXN": {"symbol": "MX$", "name": "Mexican Peso"},
            "ARS": {"symbol": "AR$", "name": "Argentine Peso"},
            "CLP": {"symbol": "CL$", "name": "Chilean Peso"},
            "ZAR": {"symbol": "R", "name": "South African Rand"},
            "EGP": {"symbol": "E£", "name": "Egyptian Pound"},
            "TRY": {"symbol": "₺", "name": "Turkish Lira"},
            "RUB": {"symbol": "₽", "name": "Russian Ruble"},
            "CHF": {"symbol": "CHF", "name": "Swiss Franc"},
            "NOK": {"symbol": "kr", "name": "Norwegian Krone"},
            "SEK": {"symbol": "kr", "name": "Swedish Krona"},
            "DKK": {"symbol": "kr", "name": "Danish Krone"},
            "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar"},
            "ILS": {"symbol": "₪", "name": "Israeli Shekel"},
            "AED": {"symbol": "د.إ", "name": "UAE Dirham"},
            "SAR": {"symbol": "﷼", "name": "Saudi Riyal"},
            "QAR": {"symbol": "﷼", "name": "Qatari Riyal"},
            "KWD": {"symbol": "د.ك", "name": "Kuwaiti Dinar"},
            "BHD": {"symbol": "د.ب", "name": "Bahraini Dinar"},
            "OMR": {"symbol": "﷼", "name": "Omani Rial"},
            "BDT": {"symbol": "৳", "name": "Bangladeshi Taka"},
            "PKR": {"symbol": "₨", "name": "Pakistani Rupee"},
            "LKR": {"symbol": "₨", "name": "Sri Lankan Rupee"},
            "NPR": {"symbol": "₨", "name": "Nepalese Rupee"},
            "BTN": {"symbol": "Nu.", "name": "Bhutanese Ngultrum"},
            "MMK": {"symbol": "K", "name": "Myanmar Kyat"},
            "KHR": {"symbol": "៛", "name": "Cambodian Riel"},
            "LAK": {"symbol": "₭", "name": "Lao Kip"},
            "MNT": {"symbol": "₮", "name": "Mongolian Tugrik"},
            "MOP": {"symbol": "MOP$", "name": "Macanese Pataca"}
        }
    
    def detect_currency_from_location(self, location: str) -> str:
        """Detect currency based on location name"""
        if not location:
            return settings.default_currency
            
        location_lower = location.lower().strip()
        
        # Direct country name matching
        for country, currency in self.country_currency_map.items():
            if country in location_lower:
                return currency
        
        # City-specific mappings for major cities
        city_currency_map = {
            "mumbai": "INR", "delhi": "INR", "bangalore": "INR", "chennai": "INR",
            "kolkata": "INR", "hyderabad": "INR", "pune": "INR", "ahmedabad": "INR",
            "new york": "USD", "los angeles": "USD", "chicago": "USD", "houston": "USD",
            "london": "GBP", "manchester": "GBP", "birmingham": "GBP",
            "paris": "EUR", "berlin": "EUR", "rome": "EUR", "madrid": "EUR",
            "tokyo": "JPY", "osaka": "JPY", "kyoto": "JPY",
            "singapore": "SGD", "kuala lumpur": "MYR", "bangkok": "THB",
            "jakarta": "IDR", "manila": "PHP", "ho chi minh": "VND",
            "seoul": "KRW", "beijing": "CNY", "shanghai": "CNY",
            "hong kong": "HKD", "taipei": "TWD", "macau": "MOP",
            "sydney": "AUD", "melbourne": "AUD", "toronto": "CAD",
            "vancouver": "CAD", "montreal": "CAD", "mexico city": "MXN",
            "sao paulo": "BRL", "rio de janeiro": "BRL", "buenos aires": "ARS",
            "santiago": "CLP", "lima": "PEN", "bogota": "COP",
            "cairo": "EGP", "istanbul": "TRY", "moscow": "RUB",
            "zurich": "CHF", "oslo": "NOK", "stockholm": "SEK",
            "copenhagen": "DKK", "amsterdam": "EUR", "brussels": "EUR",
            "vienna": "EUR", "prague": "CZK", "warsaw": "PLN",
            "budapest": "HUF", "bucharest": "RON", "sofia": "BGN",
            "zagreb": "HRK", "ljubljana": "EUR", "bratislava": "EUR",
            "vilnius": "EUR", "riga": "EUR", "tallinn": "EUR",
            "dublin": "EUR", "lisbon": "EUR", "athens": "EUR",
            "nicosia": "EUR", "valletta": "EUR", "luxembourg": "EUR",
            "monaco": "EUR", "san marino": "EUR", "vatican": "EUR",
            "andorra": "EUR", "liechtenstein": "CHF", "iceland": "ISK",
            "reykjavik": "ISK", "helsinki": "EUR", "tallinn": "EUR",
            "riga": "EUR", "vilnius": "EUR", "warsaw": "PLN",
            "prague": "CZK", "bratislava": "EUR", "budapest": "HUF",
            "bucharest": "RON", "sofia": "BGN", "zagreb": "HRK",
            "ljubljana": "EUR", "sarajevo": "BAM", "podgorica": "EUR",
            "skopje": "MKD", "tirana": "ALL", "belgrade": "RSD",
            "priština": "EUR", "nicosia": "EUR", "ankara": "TRY",
            "tel aviv": "ILS", "jerusalem": "ILS", "ramallah": "ILS",
            "amman": "JOD", "damascus": "SYP", "beirut": "LBP",
            "baghdad": "IQD", "tehran": "IRR", "riyadh": "SAR",
            "dubai": "AED", "abu dhabi": "AED", "doha": "QAR",
            "kuwait city": "KWD", "manama": "BHD", "muscat": "OMR",
            "sanaa": "YER", "aden": "YER", "taiz": "YER",
            "dhaka": "BDT", "karachi": "PKR", "lahore": "PKR",
            "islamabad": "PKR", "colombo": "LKR", "kathmandu": "NPR",
            "thimphu": "BTN", "yangon": "MMK", "phnom penh": "KHR",
            "vientiane": "LAK", "ulaanbaatar": "MNT", "pyongyang": "KPW",
            "taipei": "TWD", "hong kong": "HKD", "macau": "MOP",
            "ulaanbaatar": "MNT", "pyongyang": "KPW", "ulaanbaatar": "MNT"
        }
        
        for city, currency in city_currency_map.items():
            if city in location_lower:
                return currency
        
        return settings.default_currency
    
    def get_currency_info(self, currency_code: str) -> Dict[str, str]:
        """Get currency information including symbol and name"""
        return self.currency_info.get(currency_code, {
            "symbol": currency_code,
            "name": f"{currency_code} Currency"
        })
    
    def get_currency_for_trip(self, from_location: str, to_location: str) -> Tuple[str, str]:
        """Get currency for origin and destination locations"""
        from_currency = self.detect_currency_from_location(from_location)
        to_currency = self.detect_currency_from_location(to_location)
        
        # If both locations are in the same currency, return that
        if from_currency == to_currency:
            return from_currency, to_currency
        
        # For international trips, prefer destination currency
        return to_currency, from_currency
    
    def format_price(self, price: float, currency_code: str) -> str:
        """Format price with currency symbol"""
        currency_info = self.get_currency_info(currency_code)
        symbol = currency_info["symbol"]
        
        # Format based on currency
        if currency_code in ["JPY", "KRW", "VND", "IDR"]:
            # No decimal places for these currencies
            return f"{symbol}{price:,.0f}"
        else:
            # Two decimal places for most currencies
            return f"{symbol}{price:,.2f}"

# Global currency service instance
currency_service = CurrencyService()
