import React, { useState } from 'react';
import './Feedback.css';

// Add API_URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || '';

const Feedback = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    message: '',
    type: 'feedback'
  });
  const [showSuccess, setShowSuccess] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleOpen = () => {
    setIsOpen(true);
    setError('');
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
      setError('');
    }, 300);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // Clear error when user is typing
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    
    try {
      // Send data to backend API
      const response = await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify(formData)
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to submit feedback');
      }
      
      // Show success message
      setShowSuccess(true);
      
      // Reset form after 3 seconds
      setTimeout(() => {
        handleClose();
      }, 3000);
    } catch (err) {
      console.error('Error submitting feedback:', err);
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
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
                      className={error && !formData.email ? 'input-error' : ''}
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
                      className={error && !formData.message ? 'input-error' : ''}
                    />
                  </div>
                  
                  {error && (
                    <div className="error-message">
                      {error}
                    </div>
                  )}
                  
                  <button 
                    type="submit" 
                    className={`submit-button ${isSubmitting ? 'submitting' : ''}`}
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? 'Submitting...' : 'Submit'}
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