import logging

class NDIDiscovery:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NDIDiscovery, cls).__new__(cls)
            cls._instance.sources = []
        return cls._instance

    def scan(self):
        """
        Scan for NDI sources on the network.
        Returns a list of source names.
        """
        try:
            import NDIlib as ndi
            
            # This is a blocking/synchronous scan for MVP simplicity or async loop
            # Real NDI discovery usually needs a persistent finder instance.
            if not getattr(self, 'finder', None):
                ndi.initialize()
                self.finder = ndi.find_create_v2()
            
            # Wait a bit for sources? Or just query current
            # ndi.find_wait_for_sources(self.finder, 1000)
            
            sources = ndi.find_get_current_sources(self.finder)
            self.sources = [s.ndi_name for s in sources]
            return self.sources
        except ImportError:
            logging.error("NDIlib not found or SDK missing")
            return []
        except Exception as e:
            logging.error(f"Error scanning NDI sources: {e}")
            return []
