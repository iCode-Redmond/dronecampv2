from easytello import tello

drone = tello.Tello()

def setup():
    drone.takeoff()
    
def leg_one():
    for _ in range(4):
        drone.cw(90)
        drone.forward(20)
        
def leg_two():
    for _ in range(4):
        drone.ccw(90)
        drone.forward(20)
        
def leg_three():
    for _ in range(4):
        drone.up(20)
        drone.down(20)
        
def tear_down():
    drone.land()
    
def main():
    setup()
    leg_one()
    leg_two()
    leg_three()
    tear_down()
    
if __name__ == "__main__":
    main()
