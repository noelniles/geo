# What is this?
This is a program for tracking objects in an image and then transforming the 
image points into world points.

# How to use
For now the preferred way to use this is with a Python virtual environment. So,
first create a environment using your preferred method. Here is what I do:

```
python3 -m venv ~/.venvs/geo
```

This will create a virtual environment in your home directory. To activate it do this:

```
. ~/.venvs/geo/bin/activate
```

Now that the virtual environment is activated we can install the required packages. Pip makes this easy. There is a file called `requirements.txt` that contain all of the necessary imports. To install them just use do this (make sure your virtual environment is activated otherwise the packages will be install system-wide):

```
pip install -r requirements.txt
```

Once the requirements are installed you can use the main program which is called camtrak.py

# Using camtrak.py
There are a few differect modes that the program can operate in: tracking, solving, or calibrating. Right now only the tracking an solving do something.
This program is supposed to do a lot of things. Many of the components work, but
haven't been integrated into the whole. To run the program execute:
```
./camtrak.py -d [directory with images] -o [data output directory]
```
The first frame of will be displayed and then you will be asked to select a region
of interest to track or you can select control points in order to find the transform from image to world coordinate.

