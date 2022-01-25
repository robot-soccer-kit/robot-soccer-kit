#!/bin/sh

if [ -d "Maple" ]; then
    cd Maple &&
    git pull 
else
    git clone https://github.com/Rhoban/Maple.git --depth=1 
fi
