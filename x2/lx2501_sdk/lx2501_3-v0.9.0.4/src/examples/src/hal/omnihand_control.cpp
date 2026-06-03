#include <aimdk_msgs/msg/hand_command_array.hpp>
#include <chrono>
#include <cmath>
#include <memory>
#include <rclcpp/rclcpp.hpp>

using namespace std::chrono_literals;

class HandCommandPublisher : public rclcpp::Node {
public:
  HandCommandPublisher() : Node("hand_command_publisher") {
    publisher_ = this->create_publisher<aimdk_msgs::msg::HandCommandArray>(
        "/aima/hal/joint/hand/command", 10);

    // Create a timer to publish once per second
    timer_ = this->create_wall_timer(
        1s, std::bind(&HandCommandPublisher::publish_command, this));

    // Create a timer to publish once per second
    int target_finger = 0;
    int step_ = 1;
    bool increasing_ = true;
  }

private:
  void publish_command() {
    auto message = aimdk_msgs::msg::HandCommandArray();

    // Set hander
    message.header.stamp = this->now();
    message.header.frame_id = "hand_command";

    // Set the hand type
    message.left_hand_type.value = 1;  // NIMBLE_HANDS
    message.right_hand_type.value = 1; // NIMBLE_HANDS

    // Create left hand command array
    message.left_hands.resize(10);

    // Set left thumb
    message.left_hands[0].name = "left_thumb";
    message.left_hands[0].position = 0.0;
    message.left_hands[0].velocity = 0.1;
    message.left_hands[0].acceleration = 0.0;
    message.left_hands[0].deceleration = 0.0;
    message.left_hands[0].effort = 0.0;
    // Set other left fingers
    for (int i = 1; i < 10; i++) {
      message.left_hands[i].name = "left_index";
      message.left_hands[i].position = 0.0;
      message.left_hands[i].velocity = 0.1;
      message.left_hands[i].acceleration = 0.0;
      message.left_hands[i].deceleration = 0.0;
      message.left_hands[i].effort = 0.0;
    }

    // Create right hand command array
    message.right_hands.resize(10);

    // Set right thumb
    message.right_hands[0].name = "right_thumb";
    message.right_hands[0].position = 0.0;
    message.right_hands[0].velocity = 0.1;
    message.right_hands[0].acceleration = 0.0;
    message.right_hands[0].deceleration = 0.0;
    message.right_hands[0].effort = 0.0;

    // Set other right fingers (pinky)
    for (int i = 1; i < 10; i++) {
      message.right_hands[i].name = "right_pinky";
      message.right_hands[i].position = 0.0;
      message.right_hands[i].velocity = 0.1;
      message.right_hands[i].acceleration = 0.0;
      message.right_hands[i].deceleration = 0.0;
      message.right_hands[i].effort = 0.0;
    }

    if (target_finger <= 10) {
      message.right_hands[target_finger].position = 0.8;
    } else {
      int target_finger_ = target_finger - 10;
      double target_position = 0.8;
      if (target_finger_ < 3) {
        // The three thumb motors on the left hand need their signs inverted to
        // mirror the right hand's motion
        target_position = -target_position;
      }
      message.left_hands[target_finger_].position = target_position;
    }

    // Publish the message
    publisher_->publish(message);

    RCLCPP_INFO(this->get_logger(),
                "Published hand command with target_finger: %d", target_finger);

    update_target_finger();
  }

  void update_target_finger() {
    if (increasing_) {
      target_finger += step_;
      if (target_finger >= 19) {
        target_finger = 19;
        increasing_ = false;
      }
    } else {
      target_finger -= step_;
      if (target_finger <= 0) {
        target_finger = 0;
        increasing_ = true;
      }
    }
  }

  rclcpp::Publisher<aimdk_msgs::msg::HandCommandArray>::SharedPtr publisher_;
  rclcpp::TimerBase::SharedPtr timer_;

  int target_finger = 0;
  int step_ = 1;
  bool increasing_ = true;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<HandCommandPublisher>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
