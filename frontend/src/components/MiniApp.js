import React, { useEffect, useState } from 'react';
import { useTelegram } from '../context/TelegramContext';
import ModelViewerScreen from './ModelViewerScreen';

const MiniApp = () => {
  const { telegramApp, user, isReady, theme } = useTelegram();
  const [modelUrl, setModelUrl] = useState('');
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    // If Telegram is available, adjust the UI
    if (telegramApp) {
      // Enable back button if needed
      telegramApp.BackButton.show();
      telegramApp.BackButton.onClick(() => {
        // Clear model or go back to model list
        setModelUrl('');
      });
      
      // Expand the app to full height
      telegramApp.expand();
      
      // Set the main button if needed
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
    }
    
    return () => {
      // Cleanup
      if (telegramApp) {
        telegramApp.BackButton.hide();
        telegramApp.MainButton.hide();
      }
    };
  }, [telegramApp]);
  
  // When a model is loaded, hide the main button and show back button
  useEffect(() => {
    if (!telegramApp) return;
    
    if (modelUrl) {
      telegramApp.MainButton.hide();
      telegramApp.BackButton.show();
    } else {
      telegramApp.MainButton.show();
      telegramApp.BackButton.hide();
    }
  }, [modelUrl, telegramApp]);
  
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
        <ModelViewerScreen modelUrl={modelUrl} />
      ) : (
        <div className="mini-app-welcome">
          <h2>Welcome to 3D Model Viewer</h2>
          {user && <p>Hello, {user.first_name}!</p>}
          <p className="tg-hint">Use the main button to select a 3D model to view</p>
          
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