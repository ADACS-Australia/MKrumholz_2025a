class ScalingStrategy:

    @classmethod
    def _convert_to_amr_param(cls, box: list) -> str:
        value = " ".join(str(x) for x in box)
        return (f'({value})', f'amr.n_cell={value}')
    
    @classmethod
    def weak_3d_scaling(cls, init_box:list, min_cores: int, max_cores: int):
        dim = len(init_box) 
        if dim < 1:
            raise ValueError("Dimension must be >= 1.")
        
        core_dict = {}
        # start with one core
        cores = 1
        box = init_box[:]
        while cores <= max_cores:
            if cores >= min_cores:
                core_dict[cores] = cls._convert_to_amr_param(box)
            box = [x * 2 for x in box]            
            cores *= 2**dim
        return core_dict