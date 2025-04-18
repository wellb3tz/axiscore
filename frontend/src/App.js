import React from 'react';
import { BrowserRouter as Router, Switch, Route, useLocation } from 'react-router-dom';
import ModelViewerScreen from './components/ModelViewerScreen';
import MiniApp from './components/MiniApp';
import { TelegramProvider } from './context/TelegramContext';
import './styles/main.css';
import './styles/theme.css';

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
      <h1>axiscore</h1>
      <h2>3D Model Viewer for Telegram</h2>
      <p>A web application that allows users to view and interact with 3D models directly in Telegram.</p>
    </div>
  );
};

// MiniApp route - the main Telegram Mini App entry point
const MiniAppPage = () => {
  return (
    <TelegramProvider>
      <MiniApp />
    </TelegramProvider>
  );
};

// Determine the basename based on environment
const getBasename = () => {
  // In development, don't use a basename
  if (process.env.NODE_ENV === 'development') {
    return '';
  }
  // In production (GitHub Pages), use '/axiscore' without trailing slash
  return '/axiscore';
};

const App = () => {
  return (
    <Router basename={getBasename()}>
      <div className="App">
        <Switch>
          <Route path="/view" exact component={ViewerPage} />
          <Route path="/miniapp" component={MiniAppPage} />
          <Route path="/home" exact component={HomePage} />
          <Route path="/" component={MiniAppPage} />
        </Switch>
      </div>
    </Router>
  );
};

export default App;