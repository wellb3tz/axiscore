import React from 'react';
import { useHistory } from 'react-router-dom';

const BackButton = ({ redirectTo }) => {
  const history = useHistory();

  const handleClick = () => {
    if (redirectTo) {
      history.push(redirectTo);
    } else {
      history.goBack();
    }
  };

  return (
    <button onClick={handleClick} style={{ fontSize: '12px', cursor: 'pointer' }}>
      ← Back
    </button>
  );
};

export default BackButton;