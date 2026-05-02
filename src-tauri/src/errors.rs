use std::io;

#[derive(Debug, thiserror::Error)]
pub enum LanzouError {
    #[error("Request failed: {0}")]
    Network(String),
    #[error("{0}")]
    Parse(String),
    #[error("{0}")]
    Password(String),
    #[error("{0}")]
    UnsupportedLink(String),
    #[error("{0}")]
    Download(String),
    #[error("Download cancelled.")]
    Cancelled,
    #[error("{0}")]
    Storage(String),
}

impl LanzouError {
    pub fn is_cancelled(&self) -> bool {
        matches!(self, Self::Cancelled)
    }
}

impl From<reqwest::Error> for LanzouError {
    fn from(error: reqwest::Error) -> Self {
        Self::Network(error.to_string())
    }
}

impl From<io::Error> for LanzouError {
    fn from(error: io::Error) -> Self {
        Self::Storage(error.to_string())
    }
}

impl From<serde_json::Error> for LanzouError {
    fn from(error: serde_json::Error) -> Self {
        Self::Parse(error.to_string())
    }
}

impl From<url::ParseError> for LanzouError {
    fn from(error: url::ParseError) -> Self {
        Self::Parse(error.to_string())
    }
}

pub type LanzouResult<T> = Result<T, LanzouError>;
