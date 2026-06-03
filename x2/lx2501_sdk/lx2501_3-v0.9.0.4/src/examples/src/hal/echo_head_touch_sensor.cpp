//
// Created by agiuser on 2026/1/23.
//

#include <aimdk_msgs/msg/touch_state.hpp>
#include <rclcpp/rclcpp.hpp>

class TouchStateSubscriber : public rclcpp::Node {
public:
  TouchStateSubscriber() : Node("touch_state_subscriber") {
    subscription_ = this->create_subscription<aimdk_msgs::msg::TouchState>(
        "/aima/hal/sensor/touch_head", 10,
        std::bind(&TouchStateSubscriber::touch_callback, this,
                  std::placeholders::_1));

    RCLCPP_INFO(this->get_logger(), "TouchState subscriber started, listening "
                                    "to /aima/hal/sensor/touch_head");
  }

private:
  void touch_callback(const aimdk_msgs::msg::TouchState::SharedPtr msg) {
    // print message info
    RCLCPP_INFO(this->get_logger(), "Received TouchState message:");
    RCLCPP_INFO(this->get_logger(), "  Timestamp: %d.%09d",
                msg->header.stamp.sec, msg->header.stamp.nanosec);

    std::string event_str = get_event_type_string(msg->event_type);
    RCLCPP_INFO(this->get_logger(), "  Event Type: %s (%d)", event_str.c_str(),
                msg->event_type);
  }

  std::string get_event_type_string(uint8_t event_type) {
    switch (event_type) {
    case aimdk_msgs::msg::TouchState::UNKNOWN:
      return "UNKNOWN";
    case aimdk_msgs::msg::TouchState::IDLE:
      return "IDLE";
    case aimdk_msgs::msg::TouchState::TOUCH:
      return "TOUCH";
    case aimdk_msgs::msg::TouchState::SLIDE:
      return "SLIDE";
    case aimdk_msgs::msg::TouchState::PAT_ONCE:
      return "PAT_ONCE";
    case aimdk_msgs::msg::TouchState::PAT_TWICE:
      return "PAT_TWICE";
    case aimdk_msgs::msg::TouchState::PAT_TRIPLE:
      return "PAT_TRIPLE";
    default:
      return "INVALID";
    }
  }
  rclcpp::Subscription<aimdk_msgs::msg::TouchState>::SharedPtr subscription_;
};

int main(int argc, char *argv[]) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<TouchStateSubscriber>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
