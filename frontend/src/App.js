import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Switch, Route } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import InitialScreen from './components/InitialScreen';
import Register from './components/Register';
import Login from './components/Login';
import Inventory from './components/Inventory';
import Chat from './components/Chat';
import PostLogin from './components/PostLogin';
import WastelandConfirmation from './components/WastelandConfirmation';
import Wasteland from './components/Wasteland';
import Options from './components/Options';
import Looting from './components/Looting';
import SlidingMenu from './components/SlidingMenu';
import { ChatProvider } from './contexts/ChatContext';
import './styles/western-theme.css';
import './styles/shootable-button.css';
import gunshotSound from './sounds/gunshot.mp3'; // Ensure you have this sound file

const App = () => {
  const [volume, setVolume] = useState(0.1); // Set default volume to 10/100

  useEffect(() => {
    const handleShot = (e) => {
      // Play gunshot sound
      const audio = new Audio(gunshotSound);
      audio.volume = volume;
      audio.play();

      const hole = document.createElement('div');
      hole.className = 'bullet-hole';
      hole.style.left = `${e.clientX}px`;
      hole.style.top = `${e.clientY}px`;
      document.body.appendChild(hole);

      setTimeout(() => {
        hole.remove();
      }, 2000);
    };

    document.addEventListener('click', handleShot);

    return () => {
      document.removeEventListener('click', handleShot);
    };
  }, [volume]);

  return (
    <ErrorBoundary>
      <ChatProvider>
        <Router basename="/theQuickandtheDead">
          <div className="App">
            <SlidingMenu volume={volume} setVolume={setVolume} />
            <Switch>
              <Route path="/" exact component={InitialScreen} />
              <Route path="/register">
                <Register volume={volume} />
              </Route>
              <Route path="/login">
                <Login volume={volume} />
              </Route>
              <Route path="/inventory">
                <Inventory volume={volume} />
              </Route>
              <Route path="/chat">
                <Chat volume={volume} />
              </Route>
              <Route path="/post-login">
                <PostLogin volume={volume} />
              </Route>
              <Route path="/wasteland-confirmation">
                <WastelandConfirmation volume={volume} />
              </Route>
              <Route path="/wasteland">
                <Wasteland volume={volume} />
              </Route>
              <Route path="/options">
                <Options volume={volume} setVolume={setVolume} />
              </Route>
              <Route path="/looting">
                <Looting />
              </Route>
            </Switch>
          </div>
        </Router>
      </ChatProvider>
    </ErrorBoundary>
  );
};

export default App;