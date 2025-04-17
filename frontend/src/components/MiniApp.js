import React, { useEffect, useState } from 'react';
import { useTelegram } from '../context/TelegramContext';
import ModelViewerScreen from './ModelViewerScreen';

const MiniApp = () => {
  const { telegramApp, user, isReady, theme } = useTelegram();
  const [modelUrl, setModelUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [showExamples, setShowExamples] = useState(false);
  
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
      
      // Set the main button to show example models
      if (!modelUrl) {
        telegramApp.MainButton.setText('Example Models');
        telegramApp.MainButton.show();
        telegramApp.MainButton.onClick(() => {
          setShowExamples(!showExamples);
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
  }, [telegramApp, modelUrl, showExamples]);
  
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
          
          {/* Examples panel - floats above the 3D view */}
          {showExamples && (
            <div className="examples-panel" style={{
              position: 'absolute',
              top: '20px',
              left: '20px',
              right: '20px',
              background: 'rgba(255, 255, 255, 0.9)',
              borderRadius: '12px',
              padding: '15px',
              zIndex: 100,
              boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                <h3 style={{ margin: 0 }}>Example Models</h3>
                <button 
                  onClick={() => setShowExamples(false)}
                  style={{ 
                    background: 'none', 
                    border: 'none', 
                    fontSize: '20px', 
                    cursor: 'pointer',
                    color: theme.isDark ? '#fff' : '#333'
                  }}
                >
                  ×
                </button>
              </div>
              
              <div className="model-examples">
                <div className="tg-card" onClick={() => {
                  setModelUrl('https://threejs.org/examples/models/gltf/DamagedHelmet/glTF/DamagedHelmet.gltf');
                  setShowExamples(false);
                }}>
                  <div className="model-title">Damaged Helmet</div>
                  <div className="tg-hint">Click to view</div>
                </div>
                <div className="tg-card" onClick={() => {
                  setModelUrl('https://threejs.org/examples/models/gltf/Duck/glTF/Duck.gltf');
                  setShowExamples(false);
                }}>
                  <div className="model-title">Duck</div>
                  <div className="tg-hint">Click to view</div>
                </div>
                <div className="tg-card" onClick={() => {
                  setModelUrl('https://threejs.org/examples/models/gltf/Parrot.glb');
                  setShowExamples(false);
                }}>
                  <div className="model-title">Parrot</div>
                  <div className="tg-hint">Click to view</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MiniApp; 