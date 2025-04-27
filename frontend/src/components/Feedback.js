import React, { useState } from 'react';
import './Feedback.css';

const Feedback = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    message: '',
    type: 'feedback'
  });
  const [showSuccess, setShowSuccess] = useState(false);

  const handleOpen = () => {
    setIsOpen(true);
  };

  const handleClose = () => {
    setIsOpen(false);
    // Reset form after a delay to allow smooth transition
    setTimeout(() => {
      setFormData({
        email: '',
        message: '',
        type: 'feedback'
      });
      setShowSuccess(false);
    }, 300);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Here you would send data to server
    console.log('Submitting feedback:', formData);
    
    // For now we just show a success message
    setShowSuccess(true);
    
    // Reset form after 3 seconds
    setTimeout(() => {
      handleClose();
    }, 3000);
  };

  return (
    <div className="feedback-container">
      <button 
        className="feedback-button"
        onClick={handleOpen}
        aria-label="Open feedback form"
      >
        <span className="feedback-icon">💬</span>
        <span className="feedback-text">Feedback</span>
      </button>

      {isOpen && (
        <div className="feedback-overlay" onClick={handleClose}>
          <div className="feedback-modal" onClick={e => e.stopPropagation()}>
            <button className="close-button" onClick={handleClose}>×</button>
            
            {showSuccess ? (
              <div className="success-message">
                <span className="success-icon">✓</span>
                <h3>Thank you!</h3>
                <p>Your feedback has been submitted. We appreciate your input!</p>
              </div>
            ) : (
              <>
                <h2>We'd love to hear from you!</h2>
                
                <form onSubmit={handleSubmit}>
                  <div className="form-group">
                    <label htmlFor="feedback-type">Type:</label>
                    <div className="radio-group">
                      <label>
                        <input
                          type="radio"
                          name="type"
                          value="feedback"
                          checked={formData.type === 'feedback'}
                          onChange={handleChange}
                        />
                        Feedback
                      </label>
                      <label>
                        <input
                          type="radio"
                          name="type"
                          value="question"
                          checked={formData.type === 'question'}
                          onChange={handleChange}
                        />
                        Question
                      </label>
                      <label>
                        <input
                          type="radio"
                          name="type"
                          value="bug"
                          checked={formData.type === 'bug'}
                          onChange={handleChange}
                        />
                        Report a Bug
                      </label>
                    </div>
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="email">Email:</label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      placeholder="Your email address"
                      value={formData.email}
                      onChange={handleChange}
                      required
                    />
                  </div>
                  
                  <div className="form-group">
                    <label htmlFor="message">Message:</label>
                    <textarea
                      id="message"
                      name="message"
                      placeholder="Please share your thoughts, questions, or report an issue"
                      value={formData.message}
                      onChange={handleChange}
                      required
                      rows={5}
                    />
                  </div>
                  
                  <button type="submit" className="submit-button">
                    Submit
                  </button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Feedback; 