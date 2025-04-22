import React, { useEffect, useState } from 'react';
import { useTelegram } from '../context/TelegramContext';
import ModelViewerScreen from './ModelViewerScreen';

const MiniApp = () => {
  const { telegramApp, user, isReady, theme } = useTelegram();
  const [modelUrl, setModelUrl] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Get model URL from query parameters if available
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    
    // Check for regular query parameter
    let urlParam = params.get('model');
    
    // If no regular param, check for Telegram Mini App startapp parameter
    if (!urlParam && telegramApp) {
      const startParam = telegramApp.initDataUnsafe.start_param;
      if (startParam && startParam.startsWith('model__')) {
        // Extract the model URL from the start parameter
        urlParam = decodeURIComponent(startParam.substring(7));
      }
    }
    
    if (urlParam) {
      console.log("Loading model from URL:", urlParam);
      setModelUrl(urlParam);
      setLoading(true);
    }
  }, [telegramApp]);
  
  useEffect(() => {
    // If Telegram is available, adjust the UI
    if (telegramApp) {
      // Enable back button if needed
      if (modelUrl) {
        telegramApp.BackButton.show();
        telegramApp.BackButton.onClick(() => {
          // Clear model to show empty environment
          setModelUrl('');
        });
      } else {
        telegramApp.BackButton.hide();
      }
      
      // Expand the app to full height
      telegramApp.expand();
      
      // Hide the MainButton - we're removing Example Models functionality
      telegramApp.MainButton.hide();
    }
    
    return () => {
      // Cleanup
      if (telegramApp) {
        telegramApp.BackButton.hide();
        telegramApp.MainButton.hide();
      }
    };
  }, [telegramApp, modelUrl]);
  
  // Determine colors based on Telegram theme
  const isDarkTheme = theme?.isDark || false;
  const textColor = isDarkTheme ? '#ffffff' : '#333333';
  const bgColor = isDarkTheme ? 'rgba(42, 42, 42, 0.9)' : 'rgba(255, 255, 255, 0.9)';
  const accentColor = isDarkTheme ? '#8774e1' : '#5e72e4'; // Purple/blue accent color
  
  // Styled loading spinner
  const LoadingSpinner = () => (
    <div className="loading-container" style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      width: '100%',
      backgroundColor: isDarkTheme ? '#1c1c1c' : '#f8f9fa',
      color: textColor,
      position: 'absolute',
      top: 0,
      left: 0,
      zIndex: 1000
    }}>
      <div className="spinner" style={{
        width: '48px',
        height: '48px',
        border: `4px solid ${isDarkTheme ? '#333' : '#e9ecef'}`,
        borderRadius: '50%',
        borderTop: `4px solid ${accentColor}`,
        animation: 'spin 1s linear infinite',
        marginBottom: '16px'
      }}></div>
      <div style={{
        fontWeight: '500',
        fontSize: '16px',
        opacity: '0.9'
      }}>Loading 3D Model...</div>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
  
  if (!isReady) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: isDarkTheme ? '#1c1c1c' : '#f8f9fa',
        color: textColor
      }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: `3px solid ${isDarkTheme ? '#333' : '#e9ecef'}`,
          borderRadius: '50%',
          borderTop: `3px solid ${accentColor}`,
          animation: 'spin 1s linear infinite',
          marginBottom: '12px'
        }}></div>
        <div style={{ fontWeight: '500' }}>Initializing Mini App...</div>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }
  
  return (
    <div className="mini-app-container" style={{ 
      height: '100vh', 
      width: '100%', 
      overflow: 'hidden',
      position: 'relative',
      backgroundColor: isDarkTheme ? '#1c1c1c' : '#f8f9fa'
    }}>
      {loading && <LoadingSpinner />}
      
      <div className="model-viewer-container" style={{ height: '100%', width: '100%' }}>
        <ModelViewerScreen 
          modelUrl={modelUrl} 
          onLoaded={() => setLoading(false)}
          isDarkTheme={isDarkTheme}
          accentColor={accentColor}
        />
        
        {/* Download button - only show when a model is loaded */}
        {modelUrl && (
          <div className="download-button-container">
            <a 
              href={modelUrl} 
              download 
              style={{
                position: 'absolute',
                bottom: '20px',
                right: '20px',
                zIndex: 100,
                backgroundColor: accentColor,
                color: '#fff',
                padding: '10px 16px',
                borderRadius: '8px',
                textDecoration: 'none',
                fontWeight: '500',
                boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '14px'
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 15V3m0 12l-4-4m4 4l4-4M2 17l.621 2.485A2 2 0 0 0 4.561 21h14.878a2 2 0 0 0 1.94-1.515L22 17" />
              </svg>
              Download Original
            </a>
          </div>
        )}
        
        {/* Model error message - show when model fails to load */}
        {modelUrl && (
          <div 
            className="error-button" 
            style={{
              position: 'absolute',
              bottom: '20px',
              left: '20px',
              zIndex: 100
            }}
          >
            <button 
              style={{
                backgroundColor: 'transparent',
                color: textColor,
                border: `1px solid ${isDarkTheme ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)'}`,
                padding: '10px 16px',
                borderRadius: '8px',
                cursor: 'pointer',
                fontWeight: '500',
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
              onClick={() => {
                // Copy error message
                navigator.clipboard.writeText(
                  `Model URL: ${modelUrl}\nPlease report this issue to the bot developer.`
                );
                alert("Error details copied to clipboard");
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              Report Issue
            </button>
          </div>
        )}
        
        {/* Simple empty state message - when no model is loaded */}
        {!modelUrl && (
          <div 
            className="empty-state-message"
            style={{
              position: 'absolute',
              bottom: '20px',
              left: '20px',
              right: '20px',
              background: bgColor,
              color: textColor,
              borderRadius: '12px',
              padding: '20px',
              zIndex: 100,
              textAlign: 'center',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              maxWidth: '400px',
              margin: '0 auto'
            }}
          >
            <div style={{ marginBottom: '16px' }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={accentColor} strokeWidth="2" style={{ margin: '0 auto' }}>
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="7.5 4.21 12 6.81 16.5 4.21" />
                <polyline points="7.5 19.79 7.5 14.6 3 12" />
                <polyline points="21 12 16.5 14.6 16.5 19.79" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <p style={{ marginBottom: '8px', fontWeight: '600', fontSize: '16px' }}>No 3D Model Loaded</p>
            <p style={{ fontSize: '14px', opacity: '0.8', margin: 0 }}>
              Send a 3D model file (.glb, .gltf, .fbx, or .obj) to the Telegram bot to view it here.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MiniApp; 