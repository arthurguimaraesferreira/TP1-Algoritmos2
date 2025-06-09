
class KDNode:
    __slots__ = ("point", "index", "left", "right", "axis")
    def __init__(self, point, index, axis):
        # point: lista[lat, lon]
        # index: índice original no DataFrame
        # axis: dimensão de divisão (0 = latitude, 1 = longitude)

        self.point = point
        self.index = index
        self.left = None
        self.right = None
        self.axis = axis


def build_kdtree(points, depth=0) :
    # Constrói a KD-Tree recurtsivamente a partir da lista de pontos

    # Retorna a raiz (KDNode) da subárvore construída

    if not points:
        return None
    
    # 1) Define o eixo de divisão, alternando em cada nível 
    axis = depth % 2

    # 2) Ordena a lista de pontos pelo valor de coordenada no eixo escolhido
    points.sort(key=lambda x: x[0][axis])

    # 3) Escolhe o mediano para balancear a árvore
    median = len(points) // 2
    node = KDNode(point=points[median][0], index=points[median][1], axis=axis)

    # 4) Constrói recursivamente as subárvores da esquerda e da direita
    node.left = build_kdtree(points[:median], depth + 1)
    node.right = build_kdtree(points[median + 1:], depth + 1)

    return node


def range_search(node, rect, found=None):
    # Percorre a KD-Tree e coleta índices dentro do retângulo
    # Retorna lista de índices (linhas do DataFrame) cujos pontos caem dentro do retângulo

    if node is None:
        return found
    if found is None:
        found = []

    # Extrai as bordas do retângulo de busca
    (sw_lat, sw_lon), (ne_lat, ne_lon) = rect
    lat, lon = node.point

    # 1) Se o ponto armazenado neste nó estiver dentro do retângulo, adiciona o índice
    if sw_lat <= lat <= ne_lat and sw_lon <= lon <= ne_lon:
        found.append(node.index)

    axis = node.axis


    # 2) Decide se precisa visitar a subárvore esquerda (ou direita) com base no eixo:
    if axis == 0:  # comparando latitude
        if sw_lat <= lat:
            range_search(node.left, rect, found)
        if lat <= ne_lat:
            range_search(node.right, rect, found)
    else:  # comparando longitude
        if sw_lon <= lon:
            range_search(node.left, rect, found)
        if lon <= ne_lon:
            range_search(node.right, rect, found)

    return found