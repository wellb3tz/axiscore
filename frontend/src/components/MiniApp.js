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
    const urlParam = params.get('model');
    
    if (urlParam) {
      setModelUrl(urlParam);
    }
  }, []);
  
  useEffect(() => {
    // If Telegram is available, adjust the UI
    if (telegramApp) {
      // Enable back button if needed
      if (modelUrl) {
        telegramApp.BackButton.show();
      } else {
        telegramApp.BackButton.hide();
      }
      
      telegramApp.BackButton.onClick(() => {
        // Clear model or go back to model list
        setModelUrl('');
      });
      
      // Expand the app to full height
      telegramApp.expand();
      
      // Set the main button for model selection (only if no model is currently displayed)
      if (!modelUrl) {
        telegramApp.MainButton.setText('Choose 3D Model');
        telegramApp.MainButton.show();
        telegramApp.MainButton.onClick(() => {
          // Here you would implement model selection
          // For demo purposes, let's use a sample model
          setLoading(true);
          
          // Simulate loading a model
          setTimeout(() => {
            setModelUrl('https://threejs.org/examples/models/gltf/DamagedHelmet/glTF/DamagedHelmet.gltf');
            setLoading(false);
            telegramApp.MainButton.hide();
          }, 1000);
        });
      } else {
        telegramApp.MainButton.hide();
      }
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
      ) : modelUrl ? (
        <div className="model-viewer-container">
          <ModelViewerScreen modelUrl={modelUrl} />
          
          {/* Download button */}
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
        </div>
      ) : (
        <div className="mini-app-welcome">
          <h2>Welcome to 3D Model Viewer</h2>
          {user && <p>Hello, {user.first_name}!</p>}
          <p className="tg-hint">Upload a 3D model in the chat or use the examples below</p>
          
          <div className="model-examples">
            <h3>Example models:</h3>
            <div className="tg-card" onClick={() => {
              setModelUrl('https://threejs.org/examples/models/gltf/DamagedHelmet/glTF/DamagedHelmet.gltf');
            }}>
              <div className="model-title">Damaged Helmet</div>
              <div className="tg-hint">Click to view</div>
            </div>
            <div className="tg-card" onClick={() => {
              setModelUrl('https://threejs.org/examples/models/gltf/Duck/glTF/Duck.gltf');
            }}>
              <div className="model-title">Duck</div>
              <div className="tg-hint">Click to view</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MiniApp; 