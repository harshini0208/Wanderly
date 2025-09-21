import { createContext, useContext, useState, useEffect } from 'react';

const UserContext = createContext();

export const useUser = () => {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load user from localStorage on mount
    const savedUser = localStorage.getItem('wanderly_user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (error) {
        console.error('Error loading saved user:', error);
        localStorage.removeItem('wanderly_user');
      }
    }
    setIsLoading(false);
  }, []);

  const login = (userData) => {
    const userInfo = {
      id: userData.id || userData.user_id,
      name: userData.name || userData.user_name,
      email: userData.email || userData.user_email,
      joinedAt: new Date().toISOString()
    };
    
    setUser(userInfo);
    localStorage.setItem('wanderly_user', JSON.stringify(userInfo));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('wanderly_user');
  };

  const updateUser = (updates) => {
    const updatedUser = { ...user, ...updates };
    setUser(updatedUser);
    localStorage.setItem('wanderly_user', JSON.stringify(updatedUser));
  };

  const value = {
    user,
    isLoading,
    login,
    logout,
    updateUser,
    isLoggedIn: !!user
  };

  return (
    <UserContext.Provider value={value}>
      {children}
    </UserContext.Provider>
  );
};

export default UserContext;
