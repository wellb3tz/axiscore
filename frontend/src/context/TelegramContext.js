import React, { createContext, useContext, useEffect, useState } from 'react';

const TelegramContext = createContext(null);

export const TelegramProvider = ({ children }) => {
  const [telegramApp, setTelegramApp] = useState(null);
  const [user, setUser] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [theme, setTheme] = useState({
    bg_color: '#ffffff',
    text_color: '#000000',
    hint_color: '#999999',
    link_color: '#2481cc',
    button_color: '#3390ec',
    button_text_color: '#ffffff',
    isDark: false
  });

  useEffect(() => {
    // Check if Telegram WebApp is available
    if (window.Telegram && window.Telegram.WebApp) {
      const tgApp = window.Telegram.WebApp;
      
      // Initialize the WebApp
      tgApp.ready();
      setTelegramApp(tgApp);
      
      // Extract user data
      if (tgApp.initDataUnsafe && tgApp.initDataUnsafe.user) {
        setUser(tgApp.initDataUnsafe.user);
      }
      
      // Initialize theme
      if (tgApp.colorScheme) {
        setTheme({
          bg_color: tgApp.backgroundColor || '#ffffff',
          text_color: tgApp.headerColor || '#000000',
          hint_color: '#999999',
          link_color: '#2481cc',
          button_color: '#3390ec',
          button_text_color: '#ffffff',
          isDark: tgApp.colorScheme === 'dark'
        });
        
        // Apply theme to document
        document.documentElement.setAttribute('data-theme', tgApp.colorScheme);
      }
      
      setIsReady(true);
      
      // Event listeners
      tgApp.onEvent('themeChanged', () => {
        setTheme({
          bg_color: tgApp.backgroundColor || '#ffffff',
          text_color: tgApp.headerColor || '#000000',
          hint_color: '#999999',
          link_color: '#2481cc',
          button_color: '#3390ec',
          button_text_color: '#ffffff',
          isDark: tgApp.colorScheme === 'dark'
        });
        document.documentElement.setAttribute('data-theme', tgApp.colorScheme);
      });
    } else {
      // For browser debugging - simulate Telegram environment
      console.log('Telegram WebApp not available. Running in browser debug mode.');
      setIsReady(true);
    }
  }, []);

  return (
    <TelegramContext.Provider value={{ telegramApp, user, isReady, theme }}>
      {children}
    </TelegramContext.Provider>
  );
};

export const useTelegram = () => {
  const context = useContext(TelegramContext);
  if (!context) {
    throw new Error('useTelegram must be used within a TelegramProvider');
  }
  return context;
};

export default TelegramContext; 