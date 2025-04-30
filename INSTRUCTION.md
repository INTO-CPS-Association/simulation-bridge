# Instructions

Follow these steps to set up and run the **Simulation Bridge**.

## Install MATLAB Engine

First, you need to install the MATLAB Engine for Python on your computer. Follow the official instructions from MathWorks to install the MATLAB Engine API:

[MATLAB Engine API for Python Installation](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html)

## Install RabbitMQ

If you haven't installed RabbitMQ, you can do it using Homebrew on macOS. Run the following commands:

```bash
brew update
brew install rabbitmq
brew services start rabbitmq
brew services list
rabbitmqctl status
lsof -i :5672
```

This will install RabbitMQ and start the service. You can check if RabbitMQ is running using the last two commands.
