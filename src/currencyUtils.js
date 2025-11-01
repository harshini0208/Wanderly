// Currency utility functions
// Maps locations to their currency symbols

export const getCurrencyFromLocation = (location) => {
  if (!location) return '$';
  
  const locationLower = location.toLowerCase();
  const currencyMap = {
    // Europe
    'paris': '€', 'france': '€', 'london': '£', 'uk': '£', 'england': '£',
    'rome': '€', 'italy': '€', 'madrid': '€', 'spain': '€', 'berlin': '€',
    'germany': '€', 'amsterdam': '€', 'netherlands': '€', 'vienna': '€',
    'austria': '€', 'zurich': 'CHF', 'switzerland': 'CHF', 'stockholm': 'SEK',
    'sweden': 'SEK', 'oslo': 'NOK', 'norway': 'NOK', 'copenhagen': 'DKK',
    'denmark': 'DKK', 'prague': 'CZK', 'czech': 'CZK', 'budapest': 'HUF',
    'hungary': 'HUF', 'warsaw': 'PLN', 'poland': 'PLN',
    // Asia
    'tokyo': '¥', 'japan': '¥', 'seoul': '₩', 'korea': '₩', 'south korea': '₩', 'republic of korea': '₩',
    'singapore': 'S$', 'hong kong': 'HK$', 'bangkok': '฿', 'thailand': '฿',
    'mumbai': '₹', 'delhi': '₹', 'india': '₹', 'bangalore': '₹', 'kolkata': '₹',
    'chennai': '₹', 'hyderabad': '₹', 'pune': '₹', 'jaipur': '₹', 'goa': '₹',
    'ooty': '₹', 'mysore': '₹', 'coimbatore': '₹', 'kochi': '₹', 'agra': '₹',
    'varanasi': '₹', 'udaipur': '₹', 'jodhpur': '₹', 'amritsar': '₹', 'shimla': '₹',
    'kuala lumpur': 'RM', 'malaysia': 'RM', 'jakarta': 'Rp', 'indonesia': 'Rp',
    'manila': '₱', 'philippines': '₱', 'ho chi minh': '₫', 'vietnam': '₫',
    'hanoi': '₫', 'taipei': 'NT$', 'taiwan': 'NT$',
    // Americas
    'new york': '$', 'usa': '$', 'united states': '$', 'america': '$',
    'los angeles': '$', 'chicago': '$', 'miami': '$', 'san francisco': '$',
    'toronto': 'C$', 'canada': 'C$', 'vancouver': 'C$', 'montreal': 'C$',
    'mexico city': '$', 'mexico': '$', 'buenos aires': '$', 'argentina': '$',
    'sao paulo': 'R$', 'brazil': 'R$', 'rio de janeiro': 'R$', 'lima': 'S/',
    'peru': 'S/',
    // Middle East & Africa
    'dubai': 'AED', 'uae': 'AED', 'abu dhabi': 'AED', 'doha': 'QAR',
    'qatar': 'QAR', 'riyadh': 'SAR', 'saudi arabia': 'SAR', 'cairo': 'EGP',
    'egypt': 'EGP', 'istanbul': '₺', 'turkey': '₺', 'tel aviv': '₪',
    'israel': '₪', 'johannesburg': 'R', 'south africa': 'R', 'cape town': 'R',
    'nairobi': 'KSh', 'kenya': 'KSh', 'lagos': '₦', 'nigeria': '₦',
    // Oceania
    'sydney': 'A$', 'australia': 'A$', 'melbourne': 'A$', 'perth': 'A$',
    'auckland': 'NZ$', 'new zealand': 'NZ$', 'wellington': 'NZ$'
  };
  
  // Check for exact matches first
  for (const [key, currency] of Object.entries(currencyMap)) {
    if (locationLower.includes(key)) {
      return currency;
    }
  }
  
  // Check for partial matches (more flexible)
  const locationWords = locationLower.split(/\s+/);
  for (const word of locationWords) {
    for (const [key, currency] of Object.entries(currencyMap)) {
      if (word === key || key.includes(word) || word.includes(key)) {
        return currency;
      }
    }
  }
  
  // Default to USD if no match found
  return '$';
};

