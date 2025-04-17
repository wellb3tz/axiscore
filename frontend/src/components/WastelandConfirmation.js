import React from 'react';
import { useHistory } from 'react-router-dom';
import '../styles/western-theme.css';

const WastelandConfirmation = () => {
  const history = useHistory();

  const handleYes = () => {
    history.push('/wasteland');
  };

  const handleNo = () => {
    history.push('/post-login');
  };

  return (
    <div className="container">
      <h2>Do you really want to go to the wasteland? 💀</h2>
      <button onClick={handleNo}>No</button>
      <button onClick={handleYes}>Yes</button>
    </div>
  );
};

export default WastelandConfirmation;