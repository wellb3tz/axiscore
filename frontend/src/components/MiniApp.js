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
  
  if (!isReady) {
    return (
      <div className="tg-loading">
        <div className="tg-spinner"></div>
        <span>Initializing Mini App...</span>
      </div>
    );
  }
  
  return (
    <div className="mini-app-container">
      {loading ? (
        <div className="tg-loading">
          <div className="tg-spinner"></div>
          <span>Loading model...</span>
        </div>
      ) : (
        <div className="model-viewer-container">
          <ModelViewerScreen modelUrl={modelUrl} />
          
          {/* Download button - only show when a model is loaded */}
          {modelUrl && (
            <div className="download-button-container">
              <a 
                href={modelUrl} 
                download 
                className="tg-button"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  position: 'absolute',
                  bottom: '20px',
                  right: '20px',
                  zIndex: 100
                }}
              >
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
                className="tg-secondary-button"
                onClick={() => {
                  // Copy error message
                  navigator.clipboard.writeText(
                    `Model URL: ${modelUrl}\nPlease report this issue to the bot developer.`
                  );
                  alert("Error details copied to clipboard");
                }}
              >
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
                background: 'rgba(255, 255, 255, 0.9)',
                borderRadius: '12px',
                padding: '15px',
                zIndex: 100,
                textAlign: 'center'
              }}
            >
              <p>Send a 3D model file (.glb, .gltf, .fbx, or .obj) to the Telegram bot to view it here.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MiniApp; 