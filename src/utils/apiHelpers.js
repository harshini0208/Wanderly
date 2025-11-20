/**
 * API Response Normalization Utilities
 * Ensures consistent data handling across the application
 */

/**
 * Normalize suggestions response from API
 * Handles different response formats and ensures we always get an array
 * 
 * @param {any} response - The response from the API
 * @returns {Array} - Normalized array of suggestions
 */
export const normalizeSuggestionsResponse = (response) => {
  // Handle null/undefined
  if (!response) {
    console.warn('API returned null/undefined response');
    return [];
  }

  // If already an array, return it
  if (Array.isArray(response)) {
    return response;
  }

  // If it's an error object, log and return empty array
  if (response.error) {
    console.error('API returned error:', response.error);
    return [];
  }

  // If it's an object, try to extract suggestions array
  if (typeof response === 'object') {
    // Check common property names
    const suggestions = response.suggestions || 
                       response.data || 
                       response.results || 
                       response.items || 
                       [];

    if (Array.isArray(suggestions)) {
      return suggestions;
    }
  }

  // If we still don't have an array, log warning
  console.warn('Unable to normalize API response to array format:', response);
  return [];
};

/**
 * Validate suggestion object structure
 * Ensures each suggestion has required fields
 * 
 * @param {Object} suggestion - The suggestion object to validate
 * @returns {boolean} - Whether the suggestion is valid
 */
export const isValidSuggestion = (suggestion) => {
  if (!suggestion || typeof suggestion !== 'object') {
    return false;
  }

  // At minimum, should have an id or name
  return !!(suggestion.id || suggestion.name || suggestion.title);
};

/**
 * Normalize and validate suggestions array
 * 
 * @param {any} response - The response from the API
 * @returns {Array} - Validated and normalized array of suggestions
 */
export const normalizeAndValidateSuggestions = (response) => {
  const suggestions = normalizeSuggestionsResponse(response);
  return suggestions
    .filter(isValidSuggestion)
    .map(s => ({
      ...s,
      // CRITICAL: Preserve transportation-specific fields (trip_leg/leg_type)
      // Ensure both fields are set for consistency
      trip_leg: s.trip_leg || s.leg_type,
      leg_type: s.leg_type || s.trip_leg,
    }));
};

