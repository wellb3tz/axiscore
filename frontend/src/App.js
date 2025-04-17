import React from 'react';
import { BrowserRouter as Router, Switch, Route, useLocation } from 'react-router-dom';
import ModelViewerScreen from './components/ModelViewerScreen';
import './styles/main.css';

// Helper function to get URL parameters
const useQuery = () => {
  return new URLSearchParams(useLocation().search);
};

const ViewerPage = () => {
  const query = useQuery();
  const modelUrl = query.get('model');
  
  return (
    <div className="viewer-container">
      <ModelViewerScreen modelUrl={modelUrl} />
    </div>
  );
};

const HomePage = () => {
  return (
    <div className="home-container">
      <h1>3D Model Viewer for Telegram</h1>
      <p>This application allows you to view 3D models directly in Telegram.</p>
      <p>To use it, send a 3D model URL (GLTF or GLB format) to the Telegram bot.</p>
    </div>
  );
};

const App = () => {
  return (
    <Router>
      <div className="App">
        <Switch>
          <Route path="/view" exact component={ViewerPage} />
          <Route path="/" component={HomePage} />
        </Switch>
      </div>
    </Router>
  );
};

export default App;