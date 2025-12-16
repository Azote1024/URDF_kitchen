
import traceback
from NodeGraphQt import BaseNode
from utils.urdf_kitchen_config import AssemblerConfig as Config
from utils.urdf_kitchen_logger import setup_logger

logger = setup_logger("Assembler")

class BaseLinkNode(BaseNode):
    """Base link node class"""
    __identifier__ = 'insilico.nodes'
    NODE_NAME = 'BaseLinkNode'
    
    def __init__(self):
        super(BaseLinkNode, self).__init__()
        self.add_output('out')

        self.volume_value = 0.0
        self.mass_value = 0.0
        
        self.inertia = {
            'ixx': 0.0, 'ixy': 0.0, 'ixz': 0.0,
            'iyy': 0.0, 'iyz': 0.0, 'izz': 0.0
        }
        self.points = [{
            'name': 'base_link_point1',
            'type': 'fixed',
            'xyz': [0.0, 0.0, 0.0]
        }]
        self.cumulative_coords = [{
            'point_index': 0,
            'xyz': [0.0, 0.0, 0.0]
        }]

        self.stl_file = None
        self.node_color = Config.DEFAULT_NODE_COLOR
        self.rotation_axis = 0  # 0: X, 1: Y, 2: Z

    def add_input(self, name='', **kwargs):
        logger.warning("Base Link node cannot have input ports")
        return None

    def add_output(self, name='out_1', **kwargs):
        if not self.has_output(name):
            return super(BaseLinkNode, self).add_output(name, **kwargs)
        return None

    def remove_output(self, port=None):
        logger.warning("Cannot remove output port from Base Link node")
        return None

    def has_output(self, name):
        return name in [p.name() for p in self.output_ports()]

class LinkNode(BaseNode):
    """
    Generic node class representing a robot link.
    All links except BaseLink are represented as instances of this class.
    """
    __identifier__ = 'insilico.nodes'
    NODE_NAME = 'LinkNode'
    
    def __init__(self):
        super(LinkNode, self).__init__()
        self.add_input('in', color=(180, 80, 0))
        
        self.output_count = 0
        self.volume_value = 0.0
        self.mass_value = 0.0
        
        self.inertia = {
            'ixx': 0.0, 'ixy': 0.0, 'ixz': 0.0,
            'iyy': 0.0, 'iyz': 0.0, 'izz': 0.0
        }
        self.points = []
        self.cumulative_coords = []
        self.stl_file = None
        
        self.node_color = Config.DEFAULT_NODE_COLOR
        self.rotation_axis = 0  # 0: X, 1: Y, 2: Z
        
        self._add_output()

        self.set_port_deletion_allowed(True)
        self._original_double_click = self.view.mouseDoubleClickEvent
        self.view.mouseDoubleClickEvent = self.node_double_clicked

    def _add_output(self, name=''):
        if self.output_count < Config.MAX_OUTPUT_PORTS:
            self.output_count += 1
            port_name = f'out_{self.output_count}'
            super(LinkNode, self).add_output(port_name)
            
            if not hasattr(self, 'points'):
                self.points = []
            
            self.points.append({
                'name': f'point_{self.output_count}',
                'type': 'fixed',
                'xyz': [0.0, 0.0, 0.0]
            })
            
            if not hasattr(self, 'cumulative_coords'):
                self.cumulative_coords = []
                
            self.cumulative_coords.append({
                'point_index': self.output_count - 1,
                'xyz': [0.0, 0.0, 0.0]
            })
            
            logger.info(f"Added output port '{port_name}' with zero coordinates")
            return port_name

    def remove_output(self):
        if self.output_count > 1:
            port_name = f'out_{self.output_count}'
            output_port = self.get_output(port_name)
            if output_port:
                try:
                    for connected_port in output_port.connected_ports():
                        try:
                            logger.info(f"Disconnecting {port_name} from {connected_port.node().name()}.{connected_port.name()}")
                            self.graph.disconnect_node(self.id, port_name,
                                                     connected_port.node().id, connected_port.name())
                        except Exception as e:
                            logger.error(f"Error during disconnection: {str(e)}")

                    if len(self.points) >= self.output_count:
                        self.points.pop()
                        logger.info(f"Removed point data for port {port_name}")

                    if len(self.cumulative_coords) >= self.output_count:
                        self.cumulative_coords.pop()
                        logger.info(f"Removed cumulative coordinates for port {port_name}")

                    self.delete_output(output_port)
                    self.output_count -= 1
                    logger.info(f"Removed port {port_name}")

                    self.view.update()
                    
                except Exception as e:
                    logger.error(f"Error removing port and associated data: {str(e)}")
                    logger.error(traceback.format_exc())
            else:
                logger.warning(f"Output port {port_name} not found")
        else:
            logger.warning("Cannot remove the last output port")

    def node_double_clicked(self, event):
        logger.debug(f"Node {self.name()} double-clicked!")
        if hasattr(self.graph, 'show_inspector'):
            try:
                graph_view = self.graph.viewer()
                
                scene_pos = event.scenePos()
                view_pos = graph_view.mapFromScene(scene_pos)
                screen_pos = graph_view.mapToGlobal(view_pos)
                
                logger.debug(f"Double click at screen coordinates: ({screen_pos.x()}, {screen_pos.y()})")
                self.graph.show_inspector(self, screen_pos)
                
            except Exception as e:
                logger.error(f"Error getting mouse position: {str(e)}")
                logger.error(traceback.format_exc())
                self.graph.show_inspector(self)
        else:
            logger.error("Error: graph does not have show_inspector method")
