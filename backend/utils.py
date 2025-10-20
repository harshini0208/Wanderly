def get_currency_from_destination(destination):
    """Determine currency based on destination"""
    destination_lower = destination.lower()
    
    # Currency mapping based on common destinations
    currency_map = {
        # Europe
        'paris': '€', 'france': '€', 'london': '£', 'uk': '£', 'england': '£',
        'rome': '€', 'italy': '€', 'madrid': '€', 'spain': '€', 'berlin': '€',
        'germany': '€', 'amsterdam': '€', 'netherlands': '€', 'vienna': '€',
        'austria': '€', 'zurich': 'CHF', 'switzerland': 'CHF', 'stockholm': 'SEK',
        'sweden': 'SEK', 'oslo': 'NOK', 'norway': 'NOK', 'copenhagen': 'DKK',
        'denmark': 'DKK', 'prague': 'CZK', 'czech': 'CZK', 'budapest': 'HUF',
        'hungary': 'HUF', 'warsaw': 'PLN', 'poland': 'PLN',
        
        # Asia
        'tokyo': '¥', 'japan': '¥', 'seoul': '₩', 'korea': '₩', 'south korea': '₩', 'republic of korea': '₩',
        'singapore': 'S$', 'hong kong': 'HK$', 'bangkok': '฿', 'thailand': '฿',
        'mumbai': '₹', 'delhi': '₹', 'india': '₹', 'bangalore': '₹', 'kolkata': '₹',
        'chennai': '₹', 'hyderabad': '₹', 'pune': '₹', 'jaipur': '₹', 'goa': '₹',
        'ooty': '₹', 'mysore': '₹', 'coimbatore': '₹', 'kochi': '₹', 'agra': '₹',
        'varanasi': '₹', 'udaipur': '₹', 'jodhpur': '₹', 'amritsar': '₹', 'shimla': '₹',
        'kuala lumpur': 'RM', 'malaysia': 'RM', 'jakarta': 'Rp', 'indonesia': 'Rp',
        'manila': '₱', 'philippines': '₱', 'ho chi minh': '₫', 'vietnam': '₫',
        'hanoi': '₫', 'taipei': 'NT$', 'taiwan': 'NT$',
        
        # Americas
        'new york': '$', 'usa': '$', 'united states': '$', 'america': '$',
        'los angeles': '$', 'chicago': '$', 'miami': '$', 'san francisco': '$',
        'toronto': 'C$', 'canada': 'C$', 'vancouver': 'C$', 'montreal': 'C$',
        'mexico city': '$', 'mexico': '$', 'buenos aires': '$', 'argentina': '$',
        'sao paulo': 'R$', 'brazil': 'R$', 'rio de janeiro': 'R$', 'lima': 'S/',
        'peru': 'S/', 'bogota': '$', 'colombia': '$', 'santiago': '$', 'chile': '$',
        
        # Middle East & Africa
        'dubai': 'AED', 'uae': 'AED', 'abu dhabi': 'AED', 'doha': 'QAR',
        'qatar': 'QAR', 'riyadh': 'SAR', 'saudi arabia': 'SAR', 'cairo': 'EGP',
        'egypt': 'EGP', 'istanbul': '₺', 'turkey': '₺', 'tel aviv': '₪',
        'israel': '₪', 'johannesburg': 'R', 'south africa': 'R', 'cape town': 'R',
        'nairobi': 'KSh', 'kenya': 'KSh', 'lagos': '₦', 'nigeria': '₦',
        
        # Oceania
        'sydney': 'A$', 'australia': 'A$', 'melbourne': 'A$', 'perth': 'A$',
        'auckland': 'NZ$', 'new zealand': 'NZ$', 'wellington': 'NZ$'
    }
    
    # Check for exact matches first
    for key, currency in currency_map.items():
        if key in destination_lower:
            return currency
    
    # Check for partial matches (more flexible)
    destination_words = destination_lower.split()
    for word in destination_words:
        for key, currency in currency_map.items():
            if word in key or key in word:
                return currency
    
    # Default to USD if no match found
    return '$'

def get_travel_type(from_location, destination):
    """Determine if travel is domestic or international using AI"""
    if not from_location or not destination:
        return 'international'  # Default to international if missing data
    
    # Use AI to determine if travel is domestic or international
    try:
        import os
        import google.generativeai as genai
        
        # Configure Gemini AI
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return 'international'
        
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # AI prompt to determine travel type
        prompt = f"""
        Determine if travel from "{from_location}" to "{destination}" is domestic (within same country) or international (different countries).
        
        Respond with only "DOMESTIC" if both locations are in the same country, or "INTERNATIONAL" if they are in different countries.
        
        Examples:
        - Mumbai to Delhi = DOMESTIC (both in India)
        - Bangalore to Ooty = DOMESTIC (both in India)
        - New York to Los Angeles = DOMESTIC (both in USA)
        - Mumbai to Dubai = INTERNATIONAL (India to UAE)
        - London to Paris = INTERNATIONAL (UK to France)
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        
        if 'DOMESTIC' in result:
            return 'domestic'
        else:
            return 'international'
            
    except Exception as e:
        return 'international'  # Default to international on error

def get_transportation_options(travel_type):
    """Get appropriate transportation options based on travel type"""
    if travel_type == 'domestic':
        return ['Flight', 'Train', 'Bus', 'Car rental', 'Public transport', 'Mixed']
    else:  # international
        return ['Flight', 'Mixed']
