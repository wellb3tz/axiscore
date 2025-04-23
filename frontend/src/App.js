import React from 'react';
import { BrowserRouter as Router, Switch, Route } from 'react-router-dom';
import ModelViewer from './components/ModelViewer';
import './styles/main.css';
import './styles/theme.css';

const HomePage = () => {
  return (
    <div className="home-container">
      <h1>axiscore</h1>
      <h2>3D Model Viewer for Telegram</h2>
      <p>A web application that allows users to view and interact with 3D models directly in Telegram.</p>
    </div>
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
          <Route path="/view" exact component={ModelViewer} />
          <Route path="/viewer" exact component={ModelViewer} />
          <Route path="/miniapp" component={ModelViewer} />
          <Route path="/home" exact component={HomePage} />
          <Route path="/" component={ModelViewer} />
        </Switch>
      </div>
    </Router>
  );
};

export default App;