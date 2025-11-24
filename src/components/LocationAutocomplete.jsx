import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import apiService from '../api';

function LocationAutocomplete({ value, onChange, placeholder, className, required }) {
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [isLoading, setIsLoading] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 });
  const inputRef = useRef(null);
  const suggestionsRef = useRef(null);
  const debounceTimerRef = useRef(null);

  useEffect(() => {
    // Debounce API calls
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Trigger immediately when user starts typing (1+ characters)
    if (value && value.trim().length >= 1) {
      // Show loading state immediately for better UX
      setIsLoading(true);
      
      // Very short debounce (100ms) for faster response
      debounceTimerRef.current = setTimeout(async () => {
        try {
          const response = await apiService.getPlacesAutocomplete(value);
          console.log('Autocomplete response:', response);
          if (response.predictions && response.predictions.length > 0) {
            console.log('Setting suggestions:', response.predictions.length);
            setSuggestions(response.predictions);
            
            // Calculate position immediately (no delay)
            if (inputRef.current) {
              const rect = inputRef.current.getBoundingClientRect();
              const position = {
                top: rect.bottom + window.scrollY + 4,
                left: rect.left + window.scrollX,
                width: Math.max(rect.width || 200, 200)
              };
              console.log('Dropdown position calculated:', position);
              setDropdownPosition(position);
            } else {
              console.warn('Input ref not available, using fallback position');
              setDropdownPosition({
                top: 100,
                left: 0,
                width: 200
              });
            }
            // Show suggestions immediately
            console.log('Setting showSuggestions to true');
            setShowSuggestions(true);
          } else {
            setSuggestions([]);
            setShowSuggestions(false);
          }
        } catch (error) {
          console.error('Error fetching autocomplete suggestions:', error);
          setSuggestions([]);
          setShowSuggestions(false);
        } finally {
          setIsLoading(false);
        }
      }, 100); // Reduced to 100ms for much faster response
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
      setIsLoading(false);
    }

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [value]);

  useEffect(() => {
    // Close suggestions when clicking outside
    const handleClickOutside = (event) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(event.target) &&
        suggestionsRef.current &&
        !suggestionsRef.current.contains(event.target)
      ) {
        setShowSuggestions(false);
        setSelectedIndex(-1);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const updateDropdownPosition = () => {
    if (inputRef.current) {
      const rect = inputRef.current.getBoundingClientRect();
      setDropdownPosition({
        top: rect.bottom + window.scrollY + 4,
        left: rect.left + window.scrollX,
        width: Math.max(rect.width || 200, 200)
      });
    }
  };

  useEffect(() => {
    if (showSuggestions && inputRef.current) {
      // Small delay to ensure DOM is updated
      const timeoutId = setTimeout(() => {
        updateDropdownPosition();
      }, 0);
      
      // Update position on scroll and resize
      const handleScroll = () => {
        if (inputRef.current) {
          updateDropdownPosition();
        }
      };
      const handleResize = () => {
        if (inputRef.current) {
          updateDropdownPosition();
        }
      };
      
      window.addEventListener('scroll', handleScroll, true);
      window.addEventListener('resize', handleResize);
      
      return () => {
        clearTimeout(timeoutId);
        window.removeEventListener('scroll', handleScroll, true);
        window.removeEventListener('resize', handleResize);
      };
    }
  }, [showSuggestions, value]);

  const handleInputChange = (e) => {
    onChange(e.target.value);
    setSelectedIndex(-1);
  };

  const handleSelectSuggestion = (suggestion) => {
    onChange(suggestion.description);
    setShowSuggestions(false);
    setSelectedIndex(-1);
    // Blur the input to close any mobile keyboards
    if (inputRef.current) {
      inputRef.current.blur();
    }
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
          handleSelectSuggestion(suggestions[selectedIndex]);
        } else if (suggestions.length > 0) {
          handleSelectSuggestion(suggestions[0]);
        }
        break;
      case 'Escape':
        setShowSuggestions(false);
        setSelectedIndex(-1);
        break;
      default:
        break;
    }
  };

  // Debug logging
  useEffect(() => {
    console.log('LocationAutocomplete state:', {
      showSuggestions,
      suggestionsCount: suggestions.length,
      dropdownPosition,
      hasInputRef: !!inputRef.current
    });
  }, [showSuggestions, suggestions.length, dropdownPosition]);

  return (
    <div style={{ position: 'relative', width: '100%', zIndex: 1 }}>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onFocus={() => {
          // Update position and show suggestions immediately on focus
          updateDropdownPosition();
          if (suggestions.length > 0) {
            console.log('Showing suggestions on focus:', suggestions.length);
            setShowSuggestions(true);
          }
        }}
        placeholder={placeholder}
        className={className}
        required={required}
        autoComplete="off"
      />
      
      {showSuggestions && suggestions.length > 0 && createPortal(
        <div
          ref={suggestionsRef}
          style={{
            position: 'fixed',
            top: `${dropdownPosition.top || 0}px`,
            left: `${dropdownPosition.left || 0}px`,
            width: `${Math.max(dropdownPosition.width || 200, 200)}px`,
            minWidth: '200px',
            zIndex: 999999,
            backgroundColor: 'white',
            border: '1px solid #ddd',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            maxHeight: '300px',
            overflowY: 'auto',
            display: 'block',
            pointerEvents: 'auto'
          }}
        >
          {isLoading && (
            <div style={{ padding: '12px', textAlign: 'center', color: '#666' }}>
              Loading suggestions...
            </div>
          )}
          {!isLoading && suggestions.map((suggestion, index) => (
            <div
              key={suggestion.place_id || index}
              onClick={() => handleSelectSuggestion(suggestion)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                backgroundColor: selectedIndex === index ? '#f0f0f0' : 'white',
                borderBottom: index < suggestions.length - 1 ? '1px solid #eee' : 'none',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <div style={{ fontWeight: 600, color: '#333', fontSize: '0.95rem' }}>
                {suggestion.main_text || suggestion.description}
              </div>
              {suggestion.secondary_text && (
                <div style={{ fontSize: '0.85rem', color: '#666', marginTop: '2px' }}>
                  {suggestion.secondary_text}
                </div>
              )}
            </div>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}

export default LocationAutocomplete;

