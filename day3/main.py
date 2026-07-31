from easytello import tello

drone = tello.Tello()

def fly_square():
    for side in range(4):
        drone.forward(30)
        drone.cw(90)
        drone.wait(1)

def fly_triangle():
    for side in range(3):
        drone.forward(30)
        drone.cw(120)
        drone.wait(1)

def fly_rectangle():
    for side in range(4):
        if side % 2 == 0:
            drone.forward(40)
        else:
            drone.forward(20)
        drone.cw(90)
        drone.wait(1)

def fly_pentagon():
    for side in range(5):
        drone.forward(30)
        drone.cw(72)
        drone.wait(1)

def main():
    drone.takeoff()
    drone.wait(2)
    fly_square()
    fly_triangle()
    fly_rectangle()
    fly_pentagon()
    drone.land()

if __name__ == "__main__":
    main()
